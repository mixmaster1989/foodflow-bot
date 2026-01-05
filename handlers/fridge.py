"""Module for fridge management handlers.

Contains handlers for:
- Viewing fridge summary and product list
- Product detail view with pagination
- Consuming and deleting products
"""
import logging
import math
from datetime import datetime


from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram import Bot, Router, F, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, select, or_
from sqlalchemy.orm import selectinload

from database.base import get_db
from database.models import ConsumptionLog, Product, Receipt, UserSettings
from services.consultant import ConsultantService
import io

router = Router()
logger = logging.getLogger(__name__)

PAGE_SIZE: int = 10

# --- Level 2.1: Summary ---
@router.callback_query(F.data == "menu_fridge")
async def show_fridge_summary(callback: types.CallbackQuery, state: FSMContext = None) -> None:
    """Show fridge summary with total items and recently added products.

    Args:
        callback: Telegram callback query

    """
    if state:
        await state.clear() # Clear any pending states when entering main view logic
        
    user_id = callback.from_user.id

    async for session in get_db():
        # Get total items
        total_items = await session.scalar(
            select(func.count())
            .select_from(Product)
            .outerjoin(Receipt)
            .where(or_(Receipt.user_id == user_id, Product.user_id == user_id))
        ) or 0

        # Get expiring items (mock logic for now, assuming 7 days from receipt date if not set)
        # In real app, we would have expiration_date column.
        # For now, let's just show latest items as "Fresh"

        latest_stmt = (
            select(Product)
            .outerjoin(Receipt)
            .where(or_(Receipt.user_id == user_id, Product.user_id == user_id))
            .order_by(Product.id.desc())
            .limit(3)
        )
        latest_products = (await session.execute(latest_stmt)).scalars().all()

    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить еду", callback_data="fridge_add_choice")
    builder.button(text="📋 Список продуктов", callback_data="fridge_list:0")
    builder.button(text="🔍 Поиск", callback_data="fridge_search") # Placeholder
    builder.button(text="🔙 Назад", callback_data="main_menu")
    builder.adjust(1, 2, 1)

    latest_text = "\n".join([f"▫️ {p.name}" for p in latest_products]) if latest_products else "Пусто"

    # Image path for empty fridge
    empty_photo_path = types.FSInputFile("assets/empty_fridge.png")

    if total_items == 0:
        caption = (
            "🧊 <b>Твой Холодильник</b>\n\n"
            "Пока тут пусто... 🕸️\n"
            "Загрузи чек или добавь продукты вручную, чтобы я мог следить за сроками и предлагать рецепты."
        )
        # Try to edit if possible (if previous was photo), otherwise send new
        try:
            await callback.message.edit_media(
                media=types.InputMediaPhoto(media=empty_photo_path, caption=caption, parse_mode="HTML"),
                reply_markup=builder.as_markup()
            )
        except Exception:
            # If edit fails (e.g. previous was text), delete and send new photo
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=empty_photo_path,
                caption=caption,
                reply_markup=builder.as_markup(),
                parse_mode="HTML"
            )
    else:
        # If not empty, just show text summary (or maybe we need a "full fridge" image later?)
        # For now, keep text for non-empty state to avoid visual clutter or use a generic fridge icon?
        # Let's stick to text for populated fridge to focus on content, OR we could use main_menu image?
        # User asked for "Empty Fridge" image specifically.

        text = (
            f"🧊 <b>Твой Холодильник</b>\n\n"
            f"📦 Всего товаров: <b>{total_items}</b>\n\n"
            f"🆕 <b>Недавно добавленные:</b>\n"
            f"{latest_text}\n\n"
            f"<i>Нажми «Список продуктов», чтобы управлять запасами.</i>"
        )

        # If we are coming from a photo message (e.g. main menu), we must delete it and send text,
        # OR edit it to text (which is not possible if it was a photo message, we can only edit caption).
        # Actually, we can edit media to something else, but we don't have a "full fridge" image.
        # So we should probably delete and send text.

        try:
            # Try to edit text (works if previous was text)
            await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        except Exception:
            # If previous was photo, we can't edit_text a photo message.
            # We must delete and send new text message.
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")

    await callback.answer()

# --- Level 2.2: List ---
@router.callback_query(F.data.startswith("fridge_list:"))
async def show_fridge_list(callback: types.CallbackQuery) -> None:
    """Show paginated list of products in fridge.

    Args:
        callback: Telegram callback query with data format "fridge_list:page"

    """
    try:
        page = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        page = 0

    user_id = callback.from_user.id

    async for session in get_db():
        # Get total for pagination
        total_items = await session.scalar(
            select(func.count())
            .select_from(Product)
            .outerjoin(Receipt)
            .where(or_(Receipt.user_id == user_id, Product.user_id == user_id))
        ) or 0

        if total_items == 0:
            await callback.answer("Холодильник пуст!", show_alert=True)
            return

        total_pages = math.ceil(total_items / PAGE_SIZE)
        page = max(0, min(page, total_pages - 1))

        stmt = (
            select(Product)
            .outerjoin(Receipt)
            .where(or_(Receipt.user_id == user_id, Product.user_id == user_id))
            .order_by(Product.id.desc())
            .offset(page * PAGE_SIZE)
            .limit(PAGE_SIZE)
        )
        products = (await session.execute(stmt)).scalars().all()

    builder = InlineKeyboardBuilder()

    # Product buttons (include page number for navigation back)
    for product in products:
        # Truncate name
        name = product.name[:25] + "..." if len(product.name) > 25 else product.name
        builder.button(text=f"▫️ {name}", callback_data=f"fridge_item:{product.id}:{page}")

    builder.adjust(1) # 1 column for better readability of names

    # Navigation row
    nav_buttons = []
    if page > 0:
        nav_buttons.append(types.InlineKeyboardButton(text="⬅️", callback_data=f"fridge_list:{page-1}"))

    nav_buttons.append(types.InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="noop"))

    if page < total_pages - 1:
        nav_buttons.append(types.InlineKeyboardButton(text="➡️", callback_data=f"fridge_list:{page+1}"))

    builder.row(*nav_buttons)
    builder.row(types.InlineKeyboardButton(text="🔙 Назад", callback_data="menu_fridge")) # Back to Summary

    await callback.message.edit_text(
        f"📋 <b>Список продуктов</b> (Стр. {page+1})",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "noop")
async def noop_handler(callback: types.CallbackQuery) -> None:
    """Handle no-op callbacks (e.g., page number display button).

    Args:
        callback: Telegram callback query

    """
    await callback.answer()

# --- Level 2.3: Item Detail ---
@router.callback_query(F.data.startswith("fridge_item:"))
async def show_item_detail(callback: types.CallbackQuery) -> None:
    """Show product detail view with pagination support.

    Callback data format: "fridge_item:product_id" or "fridge_item:product_id:page"
    """
    try:
        # Parse callback data: "fridge_item:product_id" or "fridge_item:product_id:page"
        parts = callback.data.split(":")
        product_id = int(parts[1])
        page = int(parts[2]) if len(parts) > 2 else 0
    except (IndexError, ValueError):
        await callback.answer("Ошибка", show_alert=True)
        return

    async for session in get_db():
        from sqlalchemy.orm import selectinload
        product = await session.get(Product, product_id, options=[selectinload(Product.receipt)])
        
        # Safe access to relation
        owner_id = product.user_id
        if product.receipt:
             owner_id = product.receipt.user_id
        if not product or owner_id != callback.from_user.id:
            await callback.answer("Товар не найден", show_alert=True)
            # Refresh list with saved page
            from types import SimpleNamespace
            new_callback = SimpleNamespace()
            new_callback.data = f"fridge_list:{page}"
            new_callback.from_user = callback.from_user
            new_callback.message = callback.message
            new_callback.answer = callback.answer
            await show_fridge_list(new_callback)
            return

        text = (
            f"📦 <b>{product.name}</b>\n\n"
            f"💰 Цена: {product.price}₽\n"
            f"⚖️ Кол-во: {product.quantity} шт\n"
            f"🏷️ Категория: {product.category or 'Нет'}\n\n"
            f"📊 <b>КБЖУ (на 100г):</b>\n"
            f"🔥 {product.calories} | 🥩 {product.protein} | 🥑 {product.fat} | 🍞 {product.carbs}"
        )

        builder = InlineKeyboardBuilder()
        builder.button(text="🍽️ Съесть (1 шт)", callback_data=f"fridge_eat:{product.id}:{page}")
        builder.button(text="🗑️ Удалить полностью", callback_data=f"fridge_del:{product.id}:{page}")
        # builder.button(text="🤖 Совет AI", callback_data=f"fridge_advice:{product.id}:{page}")
        builder.button(text="🔙 Назад к списку", callback_data=f"fridge_list:{page}")
        builder.adjust(1)

        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        await callback.answer()

# --- Actions ---
@router.callback_query(F.data.startswith("fridge_eat:"))
async def eat_product(callback: types.CallbackQuery) -> None:
    """Mark product as consumed (decrease quantity by 1) and refresh the view.

    Callback data format: "fridge_eat:product_id:page"
    """
    try:
        parts = callback.data.split(":")
        product_id = int(parts[1])
        page = int(parts[2]) if len(parts) > 2 else 0
    except (IndexError, ValueError):
        await callback.answer("Ошибка", show_alert=True)
        return

    async for session in get_db():
        product = await session.get(Product, product_id, options=[selectinload(Product.receipt)])
        
        owner_id = product.user_id
        if product and product.receipt:
             owner_id = product.receipt.user_id

        if not product or owner_id != callback.from_user.id:
            await callback.answer("Товар не найден", show_alert=True)
            return

        # Log consumption
        log = ConsumptionLog(
            user_id=callback.from_user.id,
            product_name=product.name,
            calories=product.calories,
            protein=product.protein,
            fat=product.fat,
            carbs=product.carbs,
            date=datetime.utcnow()
        )
        session.add(log)

        # Decrease quantity
        if product.quantity > 1:
            product.quantity -= 1
            msg = f"✅ Съел 1 шт. Осталось: {product.quantity}"
            product_still_exists = True
        else:
            await session.delete(product)
            msg = "✅ Съел последнее! Товар удален."
            product_still_exists = False

        await session.commit()
        await callback.answer(msg, show_alert=True)

        # Refresh view: return to detail if product still exists, otherwise return to list
        if product_still_exists:
            # Refresh detail view with updated quantity
            # Create a new callback query with updated data
            from types import SimpleNamespace
            new_callback = SimpleNamespace()
            new_callback.data = f"fridge_item:{product_id}:{page}"
            new_callback.from_user = callback.from_user
            new_callback.message = callback.message
            new_callback.answer = callback.answer
            await show_item_detail(new_callback)
        else:
            # Return to list on the same page
            # Create a new callback query with updated data
            from types import SimpleNamespace
            new_callback = SimpleNamespace()
            new_callback.data = f"fridge_list:{page}"
            new_callback.from_user = callback.from_user
            new_callback.message = callback.message
            new_callback.answer = callback.answer
            await show_fridge_list(new_callback)

@router.callback_query(F.data.startswith("fridge_del:"))
async def delete_product(callback: types.CallbackQuery) -> None:
    """Delete product completely and return to list.

    Callback data format: "fridge_del:product_id:page"
    """
    try:
        parts = callback.data.split(":")
        product_id = int(parts[1])
        page = int(parts[2]) if len(parts) > 2 else 0
    except (IndexError, ValueError):
        await callback.answer("Ошибка", show_alert=True)
        return

    async for session in get_db():
        product = await session.get(Product, product_id, options=[selectinload(Product.receipt)])
        
        owner_id = product.user_id
        if product and product.receipt:
             owner_id = product.receipt.user_id

        if product and owner_id == callback.from_user.id:
            await session.delete(product)
            await session.commit()
            await callback.answer("🗑️ Товар удален", show_alert=True)
        else:
            await callback.answer("Товар не найден", show_alert=True)

    # Return to list on the same page
    # Create a new callback query with updated data
    from types import SimpleNamespace
    new_callback = SimpleNamespace()
    new_callback.data = f"fridge_list:{page}"
    new_callback.from_user = callback.from_user
    new_callback.message = callback.message
    new_callback.answer = callback.answer
    await show_fridge_list(new_callback)


@router.callback_query(F.data.startswith("fridge_advice:"))
async def fridge_advice_handler(callback: types.CallbackQuery, state: types.Message = None) -> None:
    """Generate and show AI advice for a specific product.
    
    Callback data: "fridge_advice:product_id:page"
    """
    try:
        parts = callback.data.split(":")
        product_id = int(parts[1])
        page = int(parts[2]) if len(parts) > 2 else 0
    except (IndexError, ValueError):
        await callback.answer("Ошибка данных", show_alert=True)
        return

    # Notify user we are thinking
    await callback.answer("🤖 Думаю... (3-5 сек)", show_alert=True) # Alert to show interaction immediately
    
    # Or edit text to show loading state? 
    # Better to keep the current view and just append advice or send a new message?
    # User expects advice *for this item*. 
    # Let's send a temporary "Typing..." action or just edit the message text with "Loading..."
    
    async for session in get_db():
        from sqlalchemy.orm import selectinload
        product = await session.get(Product, product_id, options=[selectinload(Product.receipt)])
        
        # Safe access
        owner_id = product.user_id
        if product and product.receipt:
             owner_id = product.receipt.user_id

        if not product or owner_id != callback.from_user.id:
            await callback.answer("Товар не найден", show_alert=True)
            return

        # Prepare context (User Settings + Snapshot)
        settings_stmt = select(UserSettings).where(UserSettings.user_id == callback.from_user.id)
        settings_result = await session.execute(settings_stmt)
        settings = settings_result.scalar_one_or_none()
        
        if not settings or not settings.is_initialized:
            await callback.answer("Сначала пройди онбординг (Настройки)", show_alert=True)
            return

        # Snapshot Logic (same as before)
        totals_row = await session.execute(
            select(
                func.sum(Product.calories),
                func.sum(Product.protein),
                func.sum(Product.fat),
                func.sum(Product.carbs),
            ).where(or_(Product.user_id == callback.from_user.id, Receipt.user_id == callback.from_user.id))
        )
        totals = totals_row.fetchone() or (0, 0, 0, 0)
        names_row = await session.execute(
            select(Product.name)
            .outerjoin(Receipt)
            .where(or_(Product.user_id == callback.from_user.id, Receipt.user_id == callback.from_user.id))
            .order_by(Product.id.desc())
            .limit(10) # More items for context
        )
        fridge_snapshot = {
            "totals": {
                "calories": totals[0] or 0,
                "protein": totals[1] or 0,
                "fat": totals[2] or 0,
                "carbs": totals[3] or 0,
            },
            "items": names_row.scalars().all(),
        }

        # Call AI
        # We can edit the message to say "Thinking..."
        # But since we want to KEEP the product view and just SHOW advice, maybe an alert is enough?
        # NO, user wants to read it. Alert is too small.
        # Let's OPEN A NEW MESSAGE or EDIT current text?
        # Editing current text is best practice.
        
        original_text = (
            f"📦 <b>{product.name}</b>\n\n"
            f"💰 Цена: {product.price}₽\n"
            f"⚖️ Кол-во: {product.quantity} шт\n"
            f"🏷️ Категория: {product.category or 'Нет'}\n\n"
            f"📊 <b>КБЖУ (на 100г):</b>\n"
            f"🔥 {product.calories} | 🥩 {product.protein} | 🥑 {product.fat} | 🍞 {product.carbs}"
        )
        
        await callback.message.edit_text(original_text + "\n\n⏳ <i>Консультант анализирует...</i>", parse_mode="HTML", reply_markup=callback.message.reply_markup)
        
        recommendations = await ConsultantService.analyze_product(
            product, settings, context="fridge", fridge_snapshot=fridge_snapshot
        )
        
        # Format Advice
        advice_text = ""
        warnings = recommendations.get("warnings", [])
        recs = recommendations.get("recommendations", [])
        
        if warnings:
            advice_text += "\n\n⚠️ <b>Важно:</b>\n" + "\n".join([f"• {w}" for w in warnings[:2]]) # Limit to 2
        if recs:
            advice_text += "\n\n💡 <b>Совет:</b>\n" + "\n".join([f"• {r}" for r in recs[:2]]) # Limit to 2
            
        if not advice_text:
            advice_text = "\n\n✅ Отличный продукт, вписывается в рацион."

        # Final Update
        builder = InlineKeyboardBuilder()
        builder.button(text="🍽️ Съесть (1 шт)", callback_data=f"fridge_eat:{product.id}:{page}")
        builder.button(text="🗑️ Удалить полностью", callback_data=f"fridge_del:{product.id}:{page}")
        # Remove AI button to prevent spam or keep it to refresh? Keep it.
        # builder.button(text="🔄 Обновить совет", callback_data=f"fridge_advice:{product.id}:{page}")
        builder.button(text="🔙 Назад к списку", callback_data=f"fridge_list:{page}")
        builder.adjust(1)
        

        await callback.message.edit_text(original_text + advice_text, parse_mode="HTML", reply_markup=builder.as_markup())


# --- Level 2.4: Add Food Logic ---

class FridgeStates(StatesGroup):
    waiting_for_add_choice = State() # Not strictly needed if using callback modes
    waiting_for_receipt_scan = State()
    waiting_for_label_photo = State()
    waiting_for_dish_photo = State()


@router.callback_query(F.data == "fridge_add_choice")
async def fridge_add_choice(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Show options for adding food."""
    builder = InlineKeyboardBuilder()
    builder.button(text="📄 Чек", callback_data="fridge_add:receipt")
    builder.button(text="🏷️ Этикетка/Продукт", callback_data="fridge_add:label")
    builder.button(text="🥘 Готовое блюдо", callback_data="fridge_add:dish")
    builder.button(text="🔙 Назад", callback_data="menu_fridge")
    builder.adjust(1)
    
    await callback.message.edit_text(
        "➕ <b>Добавить еду в холодильник</b>\n\n"
        "Выбери способ добавления:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("fridge_add:"))
async def fridge_add_mode_handler(callback: types.CallbackQuery, state: FSMContext) -> None:
    mode = callback.data.split(":")[1]
    
    if mode == "receipt":
        await state.set_state(FridgeStates.waiting_for_receipt_scan)
        text = "📄 <b>Сканирование чека</b>\n\nПришли фото чека, и я добавлю все продукты."
    elif mode == "label":
        await state.set_state(FridgeStates.waiting_for_label_photo)
        text = "🏷️ <b>Добавление продукта</b>\n\nСфотографируй этикетку или сам продукт (яблоко, молоко и т.д.)."
    elif mode == "dish":
        await state.set_state(FridgeStates.waiting_for_dish_photo)
        text = "🥘 <b>Готовое блюдо</b>\n\nСфотографируй блюдо, которое хочешь сохранить."
        
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="fridge_add_choice")
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")

# --- Handlers for Photo Inputs ---

@router.message(FridgeStates.waiting_for_receipt_scan, F.photo)
async def process_fridge_receipt(message: types.Message, bot: Bot, state: FSMContext) -> None:
    """Delegate to existing receipt processing logic."""
    from handlers.receipt import _process_receipt_flow
    await state.clear() # Clear state before processing to avoid conflicts
    status_msg = await message.answer("⏳ Анализирую чек...")
    await _process_receipt_flow(message, bot, status_msg, message, None)


@router.message(FridgeStates.waiting_for_label_photo, F.photo)
async def process_fridge_label(message: types.Message, bot: Bot, state: FSMContext) -> None:
    status_msg = await message.answer("⏳ Распознаю продукт...")
    
    try:
        photo = message.photo[-1]
        file_info = await bot.get_file(photo.file_id)
        photo_bytes = io.BytesIO()
        await bot.download_file(file_info.file_path, photo_bytes)

        from services.ai import AIService
        product_data = await AIService.recognize_product_from_image(photo_bytes.getvalue())
        
        if not product_data or not product_data.get("name"):
            raise ValueError("Не удалось распознать. Попробуй еще раз.")

        user_id = message.from_user.id
        
        # Save Product
        async for session in get_db():
            product = Product(
                user_id=user_id,
                source="manual_label",
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
            
        await state.clear()
        
        builder = InlineKeyboardBuilder()
        builder.button(text="➕ Добавить еще", callback_data="fridge_add:label")
        builder.button(text="🔙 В холодильник", callback_data="menu_fridge")
        builder.adjust(1)

        await status_msg.edit_text(
            f"✅ <b>Добавлено:</b> {product_data['name']}\n"
            f"🔥 {product_data.get('calories')} ккал",
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )

    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка: {e}")


@router.message(FridgeStates.waiting_for_dish_photo, F.photo)
async def process_fridge_dish(message: types.Message, bot: Bot, state: FSMContext) -> None:
    status_msg = await message.answer("⏳ Анализирую блюдо...")

    try:
        photo = message.photo[-1]
        file_info = await bot.get_file(photo.file_id)
        photo_bytes = io.BytesIO()
        await bot.download_file(file_info.file_path, photo_bytes)

        from services.ocr import OCRService # Or use shared AI service if needed
        # Use simpler AI recognition or reused logic
        from services.ai import AIService
        
        # Using recognize_product_from_image as it fits "Dish" too (it asks for name and macros)
        product_data = await AIService.recognize_product_from_image(photo_bytes.getvalue())
        
        if not product_data or not product_data.get("name"):
            raise ValueError("Не удалось распознать блюдо.")

        user_id = message.from_user.id
        
        # Save as Product (Dish)
        async for session in get_db():
            product = Product(
                user_id=user_id,
                source="manual_dish",
                name=product_data.get("name"),
                category="Dish",
                calories=float(product_data.get("calories", 0)),
                protein=float(product_data.get("protein", 0)),
                fat=float(product_data.get("fat", 0)),
                carbs=float(product_data.get("carbs", 0)),
                price=0.0,
                quantity=1.0 # One serving
            )
            session.add(product)
            await session.commit()

        await state.clear()

        builder = InlineKeyboardBuilder()
        builder.button(text="➕ Добавить еще", callback_data="fridge_add:dish")
        builder.button(text="🔙 В холодильник", callback_data="menu_fridge")
        builder.adjust(1)
        
        await status_msg.edit_text(
            f"✅ <b>Готовое блюдо добавлено:</b>\n{product_data['name']}\n"
            f"🔥 {product_data.get('calories')} ккал",
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )

    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка: {e}")
