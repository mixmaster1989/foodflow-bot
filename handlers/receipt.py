"""Module for receipt processing and photo handling handlers.

Contains:
- handle_photo: Main photo handler that routes to different actions
- process_receipt: Process receipt photo with OCR and normalization
- price_tag_action: Process price tag photo
- log_food_action: Log food consumption from photo
- _process_receipt_flow: Internal receipt processing workflow
"""
import io
import logging
from typing import Any

from aiogram import Bot, F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.base import get_db
from database.models import Product, Receipt, UserSettings
from handlers.shopping import ShoppingMode
from services.consultant import ConsultantService
from services.matching import MatchingService
from services.normalization import NormalizationService
from services.ocr import OCRService
from sqlalchemy import select
from utils.message_cleanup import schedule_message_deletion

router = Router()
logger = logging.getLogger(__name__)


@router.message(F.photo)
async def handle_photo(message: types.Message, bot: Bot, state: FSMContext) -> None:
    """Handle incoming photo message.

    Routes to shopping mode if in shopping state, otherwise shows
    action menu (receipt, price tag, food log).

    Args:
        message: Telegram message with photo
        bot: Telegram bot instance
        state: FSM context

    Returns:
        None

    """
    current_state = await state.get_state()
    
    # Если в режиме ожидания чека - обрабатываем чек
    if current_state == ShoppingMode.waiting_for_receipt.state:
        status_msg = await message.answer("⏳ Анализирую чек (Shopping Mode)...")
        await _process_receipt_flow(message, bot, status_msg, message, state)
        return
    
    # Если в режиме сканирования этикеток или ожидания фото этикетки - не обрабатываем здесь
    # (должен обработать shopping.router, который регистрируется раньше)
    if current_state in (ShoppingMode.scanning_labels.state, ShoppingMode.waiting_for_label_photo.state):
        return

    # Create Inline Keyboard
    builder = InlineKeyboardBuilder()
    builder.button(text="🧾 Это чек", callback_data="action_receipt")
    builder.button(text="❄️ В холодильник", callback_data="action_add_to_fridge")
    builder.button(text="🏷️ Это ценник (сравнить)", callback_data="action_price_tag")
    builder.button(text="🍽️ Я это съел", callback_data="action_log_food")
    builder.button(text="❌ Отмена", callback_data="action_cancel")
    builder.adjust(1) # 1 button per row

    # Save file_id in state or just pass it?
    # For simplicity, we can't easily pass the file_id in callback_data (too long).
    # We should ask the user to reply or just assume the last photo.
    # BETTER APPROACH: Reply to the photo with the menu.
    # The callback handler will need to access the original message (which is the photo).
    # But callback_query.message is the message WITH buttons (bot's message), not the user's photo.
    # However, callback_query.message.reply_to_message might be the user's photo if we reply.

    await message.reply(
        "📸 **Вижу фото!** Что с ним сделать?",
        reply_markup=builder.as_markup()
    )

@router.callback_query(F.data == "action_cancel")
async def cancel_action(callback: types.CallbackQuery) -> None:
    """Cancel current action.

    Args:
        callback: Telegram callback query

    Returns:
        None

    """
    await callback.message.delete()
    await callback.answer("Отменено")


@router.callback_query(F.data == "action_price_tag")
async def price_tag_action(callback: types.CallbackQuery, bot: Bot) -> None:
    """Process price tag photo.

    Extracts product name, price, and volume from price tag image
    and saves for price comparison.

    Args:
        callback: Telegram callback query
        bot: Telegram bot instance

    Returns:
        None

    """
    photo_message = callback.message.reply_to_message
    if not photo_message or not photo_message.photo:
        await callback.message.edit_text("❌ Ошибка: не могу найти исходное фото.")
        return

    status_msg = await callback.message.edit_text("⏳ Анализирую ценник...")

    try:
        # Download photo
        photo = photo_message.photo[-1]
        file_info = await bot.get_file(photo.file_id)
        photo_bytes = io.BytesIO()
        await bot.download_file(file_info.file_path, photo_bytes)

        # OCR processing
        from datetime import datetime as dt

        from rapidfuzz import fuzz
        from sqlalchemy import select

        from database.models import PriceTag
        from services.price_tag_ocr import PriceTagOCRService

        price_data = await PriceTagOCRService.parse_price_tag(photo_bytes.getvalue())

        if not price_data or not price_data.get("product_name") or not price_data.get("price"):
            await status_msg.edit_text("❌ Не удалось распознать ценник. Попробуй сфотографировать четче.")
            return

        # Save to database
        async for session in get_db():
            price_tag = PriceTag(
                user_id=photo_message.from_user.id,
                product_name=price_data.get("product_name"),
                volume=price_data.get("volume"),  # Save volume separately
                price=float(price_data.get("price")),
                store_name=price_data.get("store"),
                photo_date=dt.fromisoformat(price_data["date"]) if price_data.get("date") else None,
            )
            session.add(price_tag)
            await session.commit()

            # Find similar products for price comparison
            stmt = select(PriceTag).where(PriceTag.user_id == photo_message.from_user.id)
            result = await session.execute(stmt)
            all_tags = result.scalars().all()

            similar_tags = []
            for tag in all_tags:
                if tag.id == price_tag.id:
                    continue
                score = fuzz.WRatio(price_data["product_name"].lower(), tag.product_name.lower())
                if score >= 70:
                    similar_tags.append((tag, score))

            similar_tags.sort(key=lambda x: x[1], reverse=True)
            break

        # Build response
        response = (
            f"✅ <b>Ценник сохранен!</b>\n\n"
            f"📦 <b>{price_data['product_name']}</b>"
        )

        if price_data.get("volume"):
            response += f" ({price_data['volume']})"

        response += f"\n💵 {price_data['price']}р\n"

        if price_data.get("store"):
            response += f"🏪 {price_data['store']}\n"

        if similar_tags:
            # Find the most recent previous price for the same product
            most_recent = similar_tags[0][0]  # (tag, score) tuple
            price_diff = price_data["price"] - most_recent.price

            response += "\n📊 <b>История цен:</b>\n"

            if abs(price_diff) < 0.01:  # No change (accounting for float precision)
                response += f"💚 Цена не изменилась ({most_recent.price}р)\n"
            elif price_diff > 0:
                response += f"📈 Подорожал на {price_diff:.2f}р (было {most_recent.price}р)\n"
            else:
                response += f"📉 Подешевел на {abs(price_diff):.2f}р (было {most_recent.price}р)\n"

            # Show last saved date if available
            if most_recent.created_at:
                from datetime import datetime
                days_ago = (datetime.utcnow() - most_recent.created_at).days
                if days_ago == 0:
                    response += "🕐 Последнее сохранение: сегодня\n"
                elif days_ago == 1:
                    response += "🕐 Последнее сохранение: вчера\n"
                else:
                    response += f"🕐 Последнее сохранение: {days_ago} дн. назад\n"

        await status_msg.edit_text(response, parse_mode="HTML")

        # 🚀 Search for real-time prices using Perplexity
        await callback.message.answer("🔍 Ищу актуальные цены в других магазинах...")

        from services.price_search import PriceSearchService

        # Include volume in search query for accurate comparison
        search_query = price_data["product_name"]
        if price_data.get("volume"):
            search_query += f" {price_data['volume']}"

        online_prices = await PriceSearchService.search_prices(search_query)

        if online_prices and online_prices.get("prices"):
            # Check if we actually have any non-null prices
            valid_prices = [p for p in online_prices["prices"] if p.get("price")]

            if valid_prices:
                online_response = "🌐 <b>Актуальные цены в магазинах:</b>\n\n"

                for store_price in online_prices["prices"][:5]:
                    store = store_price.get("store", "Неизвестно")
                    price = store_price.get("price")
                    if price:
                        online_response += f"• {store}: {price}р\n"

                if online_prices.get("min_price"):
                    online_response += f"\n📊 Минимальная: {online_prices['min_price']}р\n"
                    online_response += f"📊 Максимальная: {online_prices['max_price']}р\n"
                    online_response += f"📊 Средняя: {online_prices['avg_price']:.2f}р\n"

                    # Compare with scanned price
                    scanned_price = price_data["price"]
                    min_online = online_prices["min_price"]

                    if scanned_price < min_online:
                        diff = min_online - scanned_price
                        online_response += f"\n🎉 <b>Отличная цена! Дешевле на {diff:.2f}р!</b>"
                    elif scanned_price > min_online:
                        diff = scanned_price - min_online
                        online_response += f"\n⚠️ В других магазинах дешевле на {diff:.2f}р"

                await callback.message.answer(online_response, parse_mode="HTML")
            else:
                # Perplexity returned stores but no prices found
                await callback.message.answer(
                    "🔍 <b>Поиск завершен</b>\n\n"
                    "К сожалению, актуальные цены на этот товар в интернете не найдены. "
                    "Возможно, товар редкий или данные недоступны.",
                    parse_mode="HTML"
                )
        elif online_prices and online_prices.get("raw_response"):
            # If Perplexity returned text instead of JSON
            import re
            raw_text = online_prices['raw_response']
            # Remove citation markers like [1], [12]
            clean_text = re.sub(r'\[\d+\]', '', raw_text)
            # Remove JSON blocks if they exist (to avoid showing raw JSON)
            clean_text = re.sub(r'\{.*\}', '', clean_text, flags=re.DOTALL)

            await callback.message.answer(
                f"🌐 <b>Информация о ценах:</b>\n\n{clean_text[:800]}",
                parse_mode="HTML"
            )
        else:
            # No response from Perplexity at all
            await callback.message.answer(
                "⚠️ <b>Не удалось получить данные о ценах</b>\n\n"
                "Сервис поиска цен временно недоступен. Попробуйте позже.",
                parse_mode="HTML"
            )

    except Exception as exc:
        await status_msg.edit_text(f"❌ Ошибка при обработке: {exc}")



class ReceiptStates(StatesGroup):
    waiting_for_portion_weight = State()


@router.callback_query(F.data == "action_log_food")
async def log_food_action(callback: types.CallbackQuery, bot: Bot, state: FSMContext) -> None:
    """Log food consumption from photo.

    Uses AI to identify dish and asks for weight.

    Args:
        callback: Telegram callback query
        bot: Telegram bot instance
        state: FSM Context

    Returns:
        None

    """
    photo_message = callback.message.reply_to_message
    if not photo_message or not photo_message.photo:
        await callback.message.edit_text("❌ Ошибка: не могу найти исходное фото.")
        return

    status_msg = await callback.message.edit_text("⏳ Анализирую блюдо...")

    try:
        photo = photo_message.photo[-1]
        file_info = await bot.get_file(photo.file_id)
        photo_bytes = io.BytesIO()
        await bot.download_file(file_info.file_path, photo_bytes)

        # Use shared AI Service for recognition
        from services.ai import AIService
        product_data = await AIService.recognize_product_from_image(photo_bytes.getvalue()) 

        if not product_data or not product_data.get("name"):
             # Fallback if AI fails
            product_data = {
                "name": "Неизвестное блюдо",
                "calories": 200, # Default per 100g
                "protein": 10,
                "fat": 10,
                "carbs": 20
            }

        # Save data to state
        await state.update_data(food_data=product_data)
        await state.set_state(ReceiptStates.waiting_for_portion_weight)

        builder = InlineKeyboardBuilder()
        builder.button(text="🚫 Нет весов (1 порция)", callback_data="food_no_scale")
        builder.button(text="❌ Отмена", callback_data="action_cancel")
        builder.adjust(1)

        await status_msg.edit_text(
            f"🍽️ <b>{product_data['name']}</b>\n\n"
            f"Сколько съели в граммах?\n"
            f"<i>(Например: 250)</i>",
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )

    except Exception as exc:
        await status_msg.edit_text(f"❌ Ошибка при обработке: {exc}")


@router.callback_query(F.data == "action_add_to_fridge")
async def add_to_fridge_action(callback: types.CallbackQuery, bot: Bot) -> None:
    """Add product to fridge from generic photo handler.

    Args:
        callback: Telegram callback query
        bot: Telegram bot instance
    """
    photo_message = callback.message.reply_to_message
    if not photo_message or not photo_message.photo:
        await callback.message.edit_text("❌ Ошибка: не могу найти исходное фото.")
        return

    status_msg = await callback.message.edit_text("⏳ Распознаю продукт для холодильника...")

    try:
        photo = photo_message.photo[-1]
        file_info = await bot.get_file(photo.file_id)
        photo_bytes = io.BytesIO()
        await bot.download_file(file_info.file_path, photo_bytes)

        from services.ai import AIService
        product_data = await AIService.recognize_product_from_image(photo_bytes.getvalue())

        if not product_data or not product_data.get("name"):
            await status_msg.edit_text("❌ Не удалось распознать продукт. Попробуйте четче сфотографировать этикетку.")
            return

        user_id = callback.from_user.id

        async for session in get_db():
            product = Product(
                user_id=user_id,
                source="manual_chat_photo",
                name=product_data.get("name"),
                category="Manual",
                calories=float(product_data.get("calories", 0)),
                protein=float(product_data.get("protein", 0)),
                fat=float(product_data.get("fat", 0)),
                carbs=float(product_data.get("carbs", 0)),
                price=0.0,
                quantity=1.0
            )
            session.add(product)
            await session.commit()
            
        builder = InlineKeyboardBuilder()
        builder.button(text="🧊 Проверить холодильник", callback_data="menu_fridge")
        builder.adjust(1)

        await status_msg.edit_text(
            f"✅ <b>Добавлено в холодильник!</b>\n\n"
            f"📦 {product_data['name']}\n"
            f"🔥 {product_data.get('calories')} ккал\n"
            f"🏷️ <i>Добавлено через быстрое фото</i>",
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )

    except Exception as exc:
        await status_msg.edit_text(f"❌ Ошибка: {exc}")


@router.callback_query(ReceiptStates.waiting_for_portion_weight, F.data == "food_no_scale")
async def log_food_no_scale(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Handle 'No scale' choice."""
    data = await state.get_data()
    product_data = data.get("food_data")
    
    if not product_data:
        await callback.message.edit_text("❌ Ошибка данных. Попробуйте снова.")
        await state.clear()
        return

    # Standard portion assumption: 300g
    weight = 300.0
    
    await _save_consumption(callback.message, callback.from_user.id, product_data, weight)
    await state.clear()


@router.message(ReceiptStates.waiting_for_portion_weight)
async def log_food_weight_input(message: types.Message, state: FSMContext) -> None:
    """Handle manual weight input."""
    try:
        weight = float(message.text.replace(",", ".").strip())
        if weight <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Пожалуйста, введите вес цифрами (в граммах).")
        return

    data = await state.get_data()
    product_data = data.get("food_data")
    
    if not product_data:
        await message.answer("❌ Ошибка данных. Попробуйте загрузить фото снова.")
        await state.clear()
        return

    await _save_consumption(message, message.from_user.id, product_data, weight)
    await state.clear()


async def _save_consumption(reply_target: types.Message, user_id: int, product_data: dict, weight: float) -> None:
    """Helper to save consumption log and answer."""
    from datetime import datetime
    from database.models import ConsumptionLog

    # Calculate macros based on weight (product_data values are per 100g)
    factor = weight / 100.0
    
    cal = float(product_data.get("calories", 0) or 0) * factor
    prot = float(product_data.get("protein", 0) or 0) * factor
    fat = float(product_data.get("fat", 0) or 0) * factor
    carbs = float(product_data.get("carbs", 0) or 0) * factor

    name = product_data.get("name", "Блюдо")

    async for session in get_db():
        log = ConsumptionLog(
            user_id=user_id,
            product_name=name,
            calories=cal,
            protein=prot,
            fat=fat,
            carbs=carbs,
            weight=weight, # Assuming ConsumptionLog has weight field? Let's check model. If not, it's fine, we log calculated values.
            date=datetime.utcnow()
        )
        session.add(log)
        await session.commit()
    
    # Reply logic
    # Try to edit if it came from callback (no way to know easily without passing arg, but reply_target is message)
    # If reply_target is passed from callback it's the bot message. If from text input it's user message.
    
    response_text = (
        f"✅ <b>Записано в дневник!</b>\n\n"
        f"🍽️ {name} ({int(weight)}г)\n"
        f"🔥 {int(cal)} ккал | 🥩 {int(prot)}г | 🥑 {int(fat)}г | 🍞 {int(carbs)}г"
    )

    try:
        # If reply_target is a bot message (from callback), edit it
        if reply_target.from_user.is_bot:
             await reply_target.edit_text(response_text, parse_mode="HTML", reply_markup=None)
        else:
             await reply_target.answer(response_text, parse_mode="HTML")
    except Exception:
        await reply_target.answer(response_text, parse_mode="HTML")

@router.callback_query(F.data == "action_receipt")
async def process_receipt(callback: types.CallbackQuery, bot: Bot, state: FSMContext) -> None:
    """Process receipt photo from action menu.

    Args:
        callback: Telegram callback query
        bot: Telegram bot instance
        state: FSM context

    Returns:
        None

    """
    # Get the original photo message
    photo_message = callback.message.reply_to_message
    if not photo_message or not photo_message.photo:
        await callback.message.edit_text("❌ Ошибка: не могу найти исходное фото.")
        return

    await _process_receipt_flow(photo_message, bot, callback.message, callback.message, state)


async def _process_receipt_flow(
    photo_message: types.Message,
    bot: Bot,
    status_message: types.Message,
    reply_target: types.Message,
    state: FSMContext | None
) -> None:
    """Internal receipt processing workflow.

    Extracts receipt data, saves products, sends summary, and handles shopping matching.

    Args:
        photo_message: Message with receipt photo
        bot: Telegram bot instance
        status_message: Message to update with status
        reply_target: Message to reply to with results
        state: FSM context (optional, for shopping mode matching)

    Returns:
        None

    """
    try:
        await status_message.edit_text("⏳ Анализирую чек... (это может занять пару секунд)")
    except Exception:
        pass

    try:
        data, normalized_items = await _extract_receipt_data(photo_message, bot)

        try:
            await status_message.edit_text("⏳ Анализирую чек... (OCR завершен, нормализую названия...)")
        except Exception:
            pass

        products, product_ids = await _save_receipt(photo_message.from_user.id, data, normalized_items)

        try:
            await status_message.delete()
        except Exception:
            pass

        await _send_receipt_summary(reply_target, bot, data, normalized_items, products)

        if state:
            await _handle_shopping_matching(state, reply_target, product_ids)

    except Exception as exc:
        try:
            await status_message.edit_text(f"❌ Ошибка при обработке: {exc}")
        except Exception:
            await reply_target.answer(f"❌ Ошибка при обработке: {exc}")


async def _extract_receipt_data(photo_message: types.Message, bot: Bot) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Extract receipt data from photo using OCR and normalization.

    Args:
        photo_message: Message with receipt photo
        bot: Telegram bot instance

    Returns:
        Tuple of (raw OCR data, normalized items list)

    """
    photo = photo_message.photo[-1]
    file_info = await bot.get_file(photo.file_id)
    photo_bytes = io.BytesIO()
    await bot.download_file(file_info.file_path, photo_bytes)
    image_data = photo_bytes.getvalue()

    data = await OCRService.parse_receipt(image_data)
    raw_items = data.get("items", [])
    normalized_items = await NormalizationService.normalize_products(raw_items)
    return data, normalized_items


async def _save_receipt(user_id: int, data: dict[str, Any], normalized_items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[int]]:
    """Save receipt and products to database.

    Args:
        user_id: Telegram user ID
        data: Raw OCR receipt data
        normalized_items: Normalized product items

    Returns:
        Tuple of (products payload list, product IDs list)

    """
    products_payload = []
    product_ids = []

    async for session in get_db():
        receipt = Receipt(
            user_id=user_id,
            raw_text=str(data),
            total_amount=data.get("total", 0.0)
        )
        session.add(receipt)
        await session.flush()

        for item in normalized_items:
            product = Product(
                receipt_id=receipt.id,
                name=item.get("name", "Unknown"),
                price=item.get("price", 0.0),
                quantity=item.get("quantity", 1.0),
                category=item.get("category", "Uncategorized"),
                calories=item.get("calories", 0.0),
                protein=item.get("protein", 0.0),
                fat=item.get("fat", 0.0),
                carbs=item.get("carbs", 0.0),
            )
            session.add(product)
            await session.flush()
            product_ids.append(product.id)
            products_payload.append(
                {
                    "id": product.id,
                    "name": product.name,
                    "price": product.price,
                    "quantity": product.quantity,
                    "category": product.category
                }
            )

        await session.commit()
        break

    return products_payload, product_ids


async def _send_receipt_summary(
    reply_target: types.Message,
    bot: Bot,
    data: dict[str, Any],
    normalized_items: list[dict[str, Any]],
    products: list[dict[str, Any]]
) -> None:
    """Send receipt summary message to user.

    Args:
        reply_target: Message to reply to
        bot: Telegram bot instance
        data: Raw OCR receipt data
        normalized_items: Normalized product items
        products: Product payload list

    Returns:
        None

    """
    # Проверяем, есть ли продукты
    products_count = len(products)
    normalized_count = len(normalized_items)
    
    user_name = reply_target.from_user.first_name or "Пользователь"
    
    # Сначала отправляем товары с кнопками коррекции (если есть)
    if products_count > 0:
        for product in products:
            builder = InlineKeyboardBuilder()
            builder.button(text="✏️ Коррекция", callback_data=f"correct_{product['id']}")

            product_msg = await reply_target.answer(
                f"▫️ <b>{product['name']}</b>\n"
                f"💵 {product['price']}р × {product['quantity']} шт\n"
                f"🏷️ {product['category']}",
                reply_markup=builder.as_markup(),
                parse_mode="HTML"
            )
            # Schedule deletion after 10 minutes
            schedule_message_deletion(product_msg, bot, user_name)

    # Затем итоговая плашка с кнопкой "Назад"
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад в меню", callback_data="main_menu")

    # Формируем сообщение в зависимости от результата
    if products_count == 0:
        # Не удалось распознать товары
        message = (
            f"⚠️ <b>Чек обработан, но товары не распознаны</b>\n\n"
            f"💰 <b>Итого:</b> {data.get('total', 0.0)}р\n"
            f"📦 <b>Позиций распознано:</b> {normalized_count}\n\n"
            f"❌ <b>Не удалось распознать товары на чеке.</b>\n\n"
            f"Попробуй:\n"
            f"• Отправить более четкое фото чека\n"
            f"• Убедиться, что текст хорошо виден\n"
            f"• Повторить попытку через несколько секунд"
        )
    elif products_count == 1:
        message = (
            f"✅ <b>Чек обработан!</b>\n\n"
            f"💰 <b>Итого:</b> {data.get('total', 0.0)}р\n"
            f"📦 <b>Позиций:</b> {products_count}\n\n"
            f"✅ Продукт добавлен в холодильник."
        )
    else:
        message = (
            f"✅ <b>Чек обработан!</b>\n\n"
            f"💰 <b>Итого:</b> {data.get('total', 0.0)}р\n"
            f"📦 <b>Позиций:</b> {products_count}\n\n"
            f"✅ Продукты добавлены в холодильник."
        )

    summary_msg = await reply_target.answer(
        message,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    # Schedule deletion after 10 minutes
    schedule_message_deletion(summary_msg, bot, user_name)

    # Add consultant recommendations if products were recognized
    if products_count > 0:
        await _send_consultant_recommendations(reply_target, bot, products, user_name)


async def _send_consultant_recommendations(
    reply_target: types.Message,
    bot: Bot,
    products: list[dict[str, Any]],
    user_name: str
) -> None:
    """Send consultant recommendations for products from receipt.

    Args:
        reply_target: Message to reply to
        bot: Telegram bot instance
        products: List of product dictionaries
        user_name: User name for message deletion

    Returns:
        None

    """
    try:
        user_id = reply_target.from_user.id

        # Get user settings
        async for session in get_db():
            stmt = select(UserSettings).where(UserSettings.user_id == user_id)
            settings = (await session.execute(stmt)).scalar_one_or_none()
            if not settings or not settings.is_initialized:
                return  # User hasn't completed onboarding

            # Get Product objects from database
            product_objects = []
            for product_dict in products:
                product_stmt = select(Product).where(Product.id == product_dict["id"])
                product_result = await session.execute(product_stmt)
                product_obj = product_result.scalar_one_or_none()
                if product_obj:
                    product_objects.append(product_obj)

            if not product_objects:
                return

            # Get recommendations
            recommendations = await ConsultantService.analyze_products(
                product_objects, settings, context="receipt"
            )

            # Build recommendation message
            warnings = recommendations.get("warnings", [])
            recs = recommendations.get("recommendations", [])
            missing = recommendations.get("missing", [])

            if not warnings and not recs and not missing:
                return  # No recommendations

            recommendation_text = "💡 <b>Рекомендации консультанта:</b>\n\n"

            if warnings:
                recommendation_text += "\n".join(warnings) + "\n\n"
            if recs:
                recommendation_text += "\n".join(recs) + "\n\n"
            if missing:
                recommendation_text += "\n".join(missing)

            rec_msg = await reply_target.answer(
                recommendation_text,
                parse_mode="HTML"
            )
            # Schedule deletion after 10 minutes
            schedule_message_deletion(rec_msg, bot, user_name)

    except Exception as e:
        logger.error(f"Error sending consultant recommendations: {e}")


async def _handle_shopping_matching(state: FSMContext, reply_target: types.Message, product_ids: list[int]) -> None:
    current_state = await state.get_state()
    data = await state.get_data()
    session_id = data.get("shopping_session_id")

    if current_state != ShoppingMode.waiting_for_receipt.state or not session_id:
        return

    result = await MatchingService.match_products(product_ids, session_id)
    await state.clear()

    if not result:
        await reply_target.answer("🛒 Сессия покупок завершена. Совпадения не найдены.")
        return

    await _send_matching_messages(reply_target, result)


async def _send_matching_messages(reply_target: types.Message, matching_result: dict[str, Any]) -> None:
    """Send matching results messages to user.

    Args:
        reply_target: Message to reply to
        matching_result: Matching result dictionary with matched/unmatched items

    Returns:
        None

    """
    matched = matching_result.get("matched", [])
    unmatched_products = matching_result.get("unmatched_products", [])
    unmatched_labels = matching_result.get("unmatched_labels", [])
    suggestions = matching_result.get("suggestions", {})

    summary_lines = ["🛒 <b>Shopping Mode: результаты сопоставления</b>"]

    if matched:
        summary_lines.append("\n✅ <b>Сопоставленные позиции:</b>")
        for pair in matched:
            summary_lines.append(
                f"• {pair['product_name']} ↔ {pair['label_name']} "
                f"({pair.get('brand') or 'без бренда'})"
            )

    if unmatched_products:
        summary_lines.append("\n❓ <b>Несопоставленные позиции из чека:</b>")
        for product in unmatched_products:
            summary_lines.append(f"• {product['name']} ({product['price']}р)")

    if unmatched_labels:
        summary_lines.append("\n❌ <b>Этикетки без совпадения:</b>")
        for label in unmatched_labels:
            summary_lines.append(f"• {label['name']} ({label.get('weight') or '—'})")

    await reply_target.answer("\n".join(summary_lines), parse_mode="HTML")

    for product in unmatched_products:
        builder = InlineKeyboardBuilder()
        builder.button(
            text="📸 Фото этикетки",
            callback_data=f"sm_request_label:{product['id']}"
        )
        builder.button(
            text="🗑️ Убрать товар",
            callback_data=f"sm_remove_product:{product['id']}"
        )
        builder.adjust(1)

        await reply_target.answer(
            "❓ <b>Не найдено совпадение:</b>\n\n"
            f"📄 {product['name']}\n"
            f"💵 {product['price']}р × {product['quantity']} шт\n\n"
            "Отправь фото этикетки или убери товар из списка.",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )

    if unmatched_labels:
        await reply_target.answer(
            "ℹ️ У тебя остались несопоставленные этикетки. "
            "Можно привязать их вручную позже через кнопки выше."
        )
