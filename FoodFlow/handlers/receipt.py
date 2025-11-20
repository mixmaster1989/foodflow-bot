import io
from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from FoodFlow.database.base import get_db
from FoodFlow.database.models import Receipt, Product
from FoodFlow.handlers.shopping import ShoppingMode
from FoodFlow.services.matching import MatchingService
from FoodFlow.services.normalization import NormalizationService
from FoodFlow.services.ocr import OCRService

router = Router()

@router.message(F.photo)
async def handle_photo(message: types.Message, bot: Bot, state: FSMContext):
    current_state = await state.get_state()
    if current_state == ShoppingMode.waiting_for_receipt.state:
        status_msg = await message.answer("⏳ Анализирую чек (Shopping Mode)...")
        await _process_receipt_flow(message, bot, status_msg, message, state)
        return

    # Create Inline Keyboard
    builder = InlineKeyboardBuilder()
    builder.button(text="🧾 Это чек", callback_data="action_receipt")
    builder.button(text="🏷️ Это ценник", callback_data="action_price_tag")
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
async def cancel_action(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.answer("Отменено")

@router.callback_query(F.data == "action_price_tag")
async def price_tag_action(callback: types.CallbackQuery, bot: Bot):
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
        from FoodFlow.services.price_tag_ocr import PriceTagOCRService
        from FoodFlow.database.models import PriceTag
        from rapidfuzz import fuzz
        from sqlalchemy import select
        from datetime import datetime as dt
        
        price_data = await PriceTagOCRService.parse_price_tag(photo_bytes.getvalue())
        
        if not price_data or not price_data.get("product_name") or not price_data.get("price"):
            await status_msg.edit_text("❌ Не удалось распознать ценник. Попробуй сфотографировать четче.")
            return
        
        # Save to database
        async for session in get_db():
            price_tag = PriceTag(
                user_id=photo_message.from_user.id,
                product_name=price_data.get("product_name"),
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
            f"📦 <b>{price_data['product_name']}</b>\n"
            f"💵 {price_data['price']}р\n"
        )
        
        if price_data.get("store"):
            response += f"🏪 {price_data['store']}\n"
        
        if similar_tags:
            response += "\n📊 <b>Сравнение цен:</b>\n"
            prices = [price_data["price"]] + [tag.price for tag, _ in similar_tags[:5]]
            min_price = min(prices)
            max_price = max(prices)
            avg_price = sum(prices) / len(prices)
            
            response += f"• Мин: {min_price}р\n"
            response += f"• Макс: {max_price}р\n"
            response += f"• Средняя: {avg_price:.2f}р\n\n"
            
            if price_data["price"] == min_price:
                response += "🎉 <b>Это самая низкая цена!</b>"
            elif price_data["price"] > avg_price:
                response += f"⚠️ Цена выше средней на {price_data['price'] - avg_price:.2f}р"
            
            response += "\n\n<b>Похожие товары:</b>\n"
            for tag, score in similar_tags[:3]:
                response += f"• {tag.product_name} - {tag.price}р"
                if tag.store_name:
                    response += f" ({tag.store_name})"
                response += "\n"
        
        await status_msg.edit_text(response, parse_mode="HTML")
        
        # 🚀 Search for real-time prices using Perplexity
        await callback.message.answer("🔍 Ищу актуальные цены в других магазинах...")
        
        from FoodFlow.services.price_search import PriceSearchService
        
        online_prices = await PriceSearchService.search_prices(price_data["product_name"])
        
        if online_prices and online_prices.get("prices"):
            online_response = f"🌐 <b>Актуальные цены в магазинах:</b>\n\n"
            
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
        elif online_prices and online_prices.get("raw_response"):
            # If Perplexity returned text instead of JSON
            await callback.message.answer(
                f"🌐 <b>Информация о ценах:</b>\n\n{online_prices['raw_response'][:500]}",
                parse_mode="HTML"
            )
        
    except Exception as exc:
        await status_msg.edit_text(f"❌ Ошибка при обработке: {exc}")


@router.callback_query(F.data == "action_log_food")
async def log_food_action(callback: types.CallbackQuery):
    await callback.answer("Функция 'Дневник питания' скоро будет!", show_alert=True)

@router.callback_query(F.data == "action_receipt")
async def process_receipt(callback: types.CallbackQuery, bot: Bot, state: FSMContext):
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
):
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

        await _send_receipt_summary(reply_target, data, normalized_items, products)

        if state:
            await _handle_shopping_matching(state, reply_target, product_ids)

    except Exception as exc:
        try:
            await status_message.edit_text(f"❌ Ошибка при обработке: {exc}")
        except Exception:
            await reply_target.answer(f"❌ Ошибка при обработке: {exc}")


async def _extract_receipt_data(photo_message: types.Message, bot: Bot):
    photo = photo_message.photo[-1]
    file_info = await bot.get_file(photo.file_id)
    photo_bytes = io.BytesIO()
    await bot.download_file(file_info.file_path, photo_bytes)
    image_data = photo_bytes.getvalue()

    data = await OCRService.parse_receipt(image_data)
    raw_items = data.get("items", [])
    normalized_items = await NormalizationService.normalize_products(raw_items)
    return data, normalized_items


async def _save_receipt(user_id: int, data: dict, normalized_items: list[dict]):
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


async def _send_receipt_summary(reply_target: types.Message, data: dict, normalized_items: list[dict], products: list[dict]):
    await reply_target.answer(
        f"✅ <b>Чек обработан!</b>\n\n"
        f"💰 <b>Итого:</b> {data.get('total', 0.0)}р\n"
        f"📦 <b>Позиций:</b> {len(normalized_items)}\n\n"
        f"Продукты добавлены в холодильник.",
        parse_mode="HTML"
    )

    for product in products:
        builder = InlineKeyboardBuilder()
        builder.button(text="✏️ Коррекция", callback_data=f"correct_{product['id']}")

        await reply_target.answer(
            f"▫️ <b>{product['name']}</b>\n"
            f"💵 {product['price']}р × {product['quantity']} шт\n"
            f"🏷️ {product['category']}",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )


async def _handle_shopping_matching(state: FSMContext, reply_target: types.Message, product_ids: list[int]):
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


async def _send_matching_messages(reply_target: types.Message, matching_result: dict):
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
        for suggestion in suggestions.get(product["id"], []):
            builder.button(
                text=f"📦 {suggestion['label_name']} ({int(suggestion['score'])}%)",
                callback_data=f"sm_link:{product['id']}:{suggestion['label_id']}"
            )
        builder.button(text="➕ Это новый товар", callback_data=f"sm_skip:{product['id']}")
        builder.adjust(1)

        await reply_target.answer(
            "❓ <b>Не найдено совпадение:</b>\n\n"
            f"📄 {product['name']}\n"
            f"💵 {product['price']}р × {product['quantity']} шт\n\n"
            "Выбери этикетку или оставь как новый товар.",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )

    if unmatched_labels:
        await reply_target.answer(
            "ℹ️ У тебя остались несопоставленные этикетки. "
            "Можно привязать их вручную позже через кнопки выше."
        )
