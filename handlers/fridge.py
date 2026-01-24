"""Module for fridge management handlers.

Contains handlers for:
- Viewing fridge summary and product list
- Product detail view with pagination
- Consuming and deleting products
"""
import logging
import math
import io
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
from services.photo_queue import PhotoQueueManager
from services.ai import AIService

router = Router()
logger = logging.getLogger(__name__)

PAGE_SIZE: int = 10

# --- Level 2.1: Summary ---
@router.callback_query(F.data == "menu_fridge")
async def show_fridge_summary(callback: types.CallbackQuery, state: FSMContext = None) -> None:
    """Show fridge summary with total items and recently added products."""
    if state:
        await state.clear()
        
    user_id = callback.from_user.id

    async for session in get_db():
        total_items = await session.scalar(
            select(func.count())
            .select_from(Product)
            .outerjoin(Receipt)
            .where(or_(Receipt.user_id == user_id, Product.user_id == user_id))
        ) or 0

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
    builder.button(text="🔍 Поиск", callback_data="fridge_search")
    builder.button(text="🔙 Назад", callback_data="main_menu")
    builder.adjust(1, 2, 1)

    latest_text = "\n".join([f"▫️ {p.name}" for p in latest_products]) if latest_products else "Пусто"
    empty_photo_path = types.FSInputFile("assets/empty_fridge.png")

    if total_items == 0:
        caption = (
            "🧊 <b>Твой Холодильник</b>\n\n"
            "Пока тут пусто... 🕸️\n"
            "Загрузи чек или добавь продукты вручную, чтобы я мог следить за сроками и предлагать рецепты."
        )
        try:
            await callback.message.edit_media(
                media=types.InputMediaPhoto(media=empty_photo_path, caption=caption, parse_mode="HTML"),
                reply_markup=builder.as_markup()
            )
        except Exception:
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=empty_photo_path,
                caption=caption,
                reply_markup=builder.as_markup(),
                parse_mode="HTML"
            )
    else:
        text = (
            f"🧊 <b>Твой Холодильник</b>\n\n"
            f"📦 Всего товаров: <b>{total_items}</b>\n\n"
            f"🆕 <b>Недавно добавленные:</b>\n"
            f"{latest_text}\n\n"
            f"<i>Нажми «Список продуктов», чтобы управлять запасами.</i>"
        )
        try:
            await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        except Exception:
            try:
                await callback.message.delete()
            except Exception:
                pass
            await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")

    await callback.answer()

# --- Level 2.2: List ---
@router.callback_query(F.data.startswith("fridge_list:"))
async def show_fridge_list(callback: types.CallbackQuery) -> None:
    """Show paginated list of products in fridge."""
    try:
        page = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        page = 0

    user_id = callback.from_user.id

    async for session in get_db():
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

    for product in products:
        name = product.name[:25] + "..." if len(product.name) > 25 else product.name
        builder.button(text=f"▫️ {name}", callback_data=f"fridge_item:{product.id}:{page}")

    builder.adjust(1)

    nav_buttons = []
    if page > 0:
        nav_buttons.append(types.InlineKeyboardButton(text="⬅️", callback_data=f"fridge_list:{page-1}"))

    nav_buttons.append(types.InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="noop"))

    if page < total_pages - 1:
        nav_buttons.append(types.InlineKeyboardButton(text="➡️", callback_data=f"fridge_list:{page+1}"))

    builder.row(*nav_buttons)
    builder.row(types.InlineKeyboardButton(text="🔙 Назад", callback_data="menu_fridge"))

    try:
        await callback.message.edit_text(
            f"📋 <b>Список продуктов</b> (Стр. {page+1})",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    except Exception:
        await callback.message.answer(
            f"📋 <b>Список продуктов</b> (Стр. {page+1})",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    await callback.answer()

@router.callback_query(F.data == "noop")
async def noop_handler(callback: types.CallbackQuery) -> None:
    await callback.answer()

# --- Level 2.3: Item Detail ---
@router.callback_query(F.data.startswith("fridge_item:"))
async def show_item_detail(callback: types.CallbackQuery) -> None:
    """Show product detail view."""
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
        if product.receipt:
             owner_id = product.receipt.user_id
        if not product or owner_id != callback.from_user.id:
            await callback.answer("Товар не найден", show_alert=True)
            from types import SimpleNamespace
            new_callback = SimpleNamespace(data=f"fridge_list:{page}", from_user=callback.from_user, message=callback.message, answer=callback.answer)
            await show_fridge_list(new_callback)
            return

        text = (
            f"📦 <b>{product.name}</b>\n\n"
            f"💰 Цена: {product.price}₽\n"
            f"⚖️ Кол-во: {product.quantity} шт\n"
            f"🏷️ Категория: {product.category or 'Нет'}\n\n"
            f"📊 <b>КБЖУ (на 100г):</b>\n"
            f"🔥 {product.calories} | 🥩 {product.protein} | 🥑 {product.fat} | 🍞 {product.carbs}\n"
            f"🥬 Клетчатка: {product.fiber}г"
        )

        builder = InlineKeyboardBuilder()
        builder.button(text="🍽️ Съесть", callback_data=f"fridge_eat:{product.id}:{page}")
        builder.button(text="🗑️ Удалить полностью", callback_data=f"fridge_del:{product.id}:{page}")
        builder.button(text="🔙 Назад к списку", callback_data=f"fridge_list:{page}")
        builder.adjust(1)

        try:
            await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        except Exception:
            await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        await callback.answer()

# --- Actions ---
@router.callback_query(F.data.startswith("fridge_eat:"))
async def show_eat_options(callback: types.CallbackQuery) -> None:
    """Show options for consumption."""
    try:
        parts = callback.data.split(":")
        product_id = int(parts[1])
        page = int(parts[2]) if len(parts) > 2 else 0
    except (IndexError, ValueError):
        await callback.answer("Ошибка", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    builder.button(text="🍽️ Целиком", callback_data=f"fridge_consume:whole:{product_id}:{page}")
    builder.button(text="⚖️ В граммах", callback_data=f"fridge_consume:grams_input:{product_id}:{page}")
    builder.button(text="🧩 В штуках", callback_data=f"fridge_consume:pieces_input:{product_id}:{page}")
    builder.button(text="🔙 Назад", callback_data=f"fridge_item:{product_id}:{page}")
    builder.adjust(1)

    await callback.message.edit_text(
        "🍽️ <b>Сколько съели?</b>\n\nВыберите вариант:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("fridge_consume:"))
async def handle_consume_choice(callback: types.CallbackQuery, state: FSMContext) -> None:
    parts = callback.data.split(":")
    mode = parts[1]
    product_id = int(parts[2])
    page = int(parts[3]) if len(parts) > 3 else 0
    
    if mode == "whole":
        await consume_product(callback, product_id, page, amount=1, unit="qty")
        
    elif mode == "grams_input":
        await state.set_state(FridgeStates.waiting_for_consume_grams)
        await state.update_data(product_id=product_id, page=page)
        await callback.message.edit_text("⚖️ <b>Введите вес (в граммах):</b>\n\nНапример: 50, 100", parse_mode="HTML")
        
    elif mode == "pieces_input":
        await state.set_state(FridgeStates.waiting_for_consume_pieces)
        await state.update_data(product_id=product_id, page=page)
        await callback.message.edit_text("🧩 <b>Введите количество (шт):</b>\n\nНапример: 0.5, 1, 2", parse_mode="HTML")


async def consume_product(callback, product_id, page, amount, unit, log_calories=None):
    """Core consumption logic."""
    async for session in get_db():
        product = await session.get(Product, product_id)
        
        if not product:
            await callback.answer("Товар не найден", show_alert=True)
            return

        calculated_calories = 0
        
        if unit == "grams":
            calculated_calories = (amount / 100) * product.calories if product.calories else 0
            
            if product.weight_g is not None:
                if product.weight_g > amount:
                    product.weight_g -= amount
                    msg = f"✅ Съедено {amount}г. Осталось: {product.weight_g:.0f}г"
                    remaining = True
                else:
                    await session.delete(product)
                    msg = f"✅ Съедено {amount}г. Продукт закончился."
                    remaining = False
            else:
                msg = f"✅ Записано: {amount}г (Вес продукта не отслеживается)"
                remaining = True

        elif unit == "qty":
            # If weight exists, reduce weight proportionally
            if product.weight_g:
                weight_per_unit = product.weight_g / product.quantity
                consumed_weight = weight_per_unit * amount
                product.weight_g -= consumed_weight
                calculated_calories = (consumed_weight / 100) * product.calories if product.calories else 0
            else:
                # Fallback: Weight unknown. Assume 100g per unit.
                estimated_weight = 100.0 * amount
                calculated_calories = (estimated_weight / 100) * product.calories if product.calories else 0
                # We can't reduce weight_g since it's None.
            
            if product.quantity > amount:
                product.quantity -= amount
                msg = f"✅ Съедено {amount} шт. Осталось: {product.quantity}"
                remaining = True
            else:
                await session.delete(product)
                msg = "✅ Продукт закончился."
                remaining = False
                
        # Log to DB
        log = ConsumptionLog(
            user_id=callback.from_user.id,
            product_name=product.name,
            calories=calculated_calories,
            protein=(calculated_calories/product.calories)*product.protein if product.calories and product.calories > 0 else 0,
            fat=(calculated_calories/product.calories)*product.fat if product.calories and product.calories > 0 else 0,
            carbs=(calculated_calories/product.calories)*product.carbs if product.calories and product.calories > 0 else 0,
            fiber=(calculated_calories/product.calories)*product.fiber if product.calories and product.calories > 0 and product.fiber else 0,
            date=datetime.utcnow()
        )
        session.add(log)
        await session.commit()
        
        if not product.weight_g and unit == "qty":
             msg += " (Вес неизвестен, считаем 100г/шт)"

        await callback.answer(msg, show_alert=True)
        
        if remaining:
             from types import SimpleNamespace
             new_callback = SimpleNamespace(data=f"fridge_item:{product_id}:{page}", from_user=callback.from_user, message=callback.message, answer=callback.answer)
             await show_item_detail(new_callback)
        else:
             from types import SimpleNamespace
             new_callback = SimpleNamespace(data=f"fridge_list:{page}", from_user=callback.from_user, message=callback.message, answer=callback.answer)
             await show_fridge_list(new_callback)

@router.callback_query(F.data.startswith("fridge_del:"))
async def delete_product(callback: types.CallbackQuery) -> None:
    """Delete product completely."""
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

    from types import SimpleNamespace
    new_callback = SimpleNamespace()
    new_callback.data = f"fridge_list:{page}"
    new_callback.from_user = callback.from_user
    new_callback.message = callback.message
    new_callback.answer = callback.answer
    await show_fridge_list(new_callback)


# --- Add Food Logic ---

class FridgeStates(StatesGroup):
    waiting_for_add_choice = State()
    waiting_for_receipt_scan = State()
    waiting_for_label_photo = State()
    waiting_for_dish_photo = State()
    waiting_for_consume_grams = State()
    waiting_for_consume_pieces = State()
    searching_fridge = State()


@router.callback_query(F.data == "fridge_add_choice")
async def fridge_add_choice(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Show options for adding food."""
    builder = InlineKeyboardBuilder()
    builder.button(text="📄 Чек", callback_data="fridge_add:receipt")
    builder.button(text="🏷️ Этикетка/Продукт", callback_data="fridge_add:label")
    builder.button(text="🥘 Готовое блюдо", callback_data="fridge_add:dish")
    builder.button(text="🔙 Назад", callback_data="menu_fridge")
    builder.adjust(1)
    
    text = (
        "➕ <b>Добавить еду в холодильник</b>\n\n"
        "Выбери способ добавления:"
    )
    
    try:
        await callback.message.edit_caption(
            caption=text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    except Exception:
        try:
            await callback.message.edit_text(
                text,
                reply_markup=builder.as_markup(),
                parse_mode="HTML"
            )
        except Exception:
            await callback.message.delete()
            await callback.message.answer(
                text,
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
    
    try:
        await callback.message.edit_caption(caption=text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        try:
            await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        except Exception:
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")


@router.message(FridgeStates.waiting_for_receipt_scan, F.photo)
async def process_fridge_receipt(message: types.Message, bot: Bot, state: FSMContext) -> None:
    from handlers.receipt import _process_receipt_flow
    await state.clear()
    status_msg = await message.answer("⏳ Анализирую чек...")
    await _process_receipt_flow(message, bot, status_msg, message, None)


@router.message(FridgeStates.waiting_for_label_photo, F.photo)
async def process_fridge_label(message: types.Message, bot: Bot, state: FSMContext) -> None:
    from services.photo_queue import PhotoQueueManager
    await PhotoQueueManager.add_item(
        user_id=message.from_user.id,
        message=message,
        bot=bot,
        state=state,
        processing_func=process_single_label,
        file_id=message.photo[-1].file_id
    )

async def process_single_label(message: types.Message, bot: Bot, state: FSMContext, file_id: str) -> None:
    status_msg = await message.answer("⏳ Распознаю продукт...")
    try:
        file_info = await bot.get_file(file_id)
        photo_bytes = io.BytesIO()
        await bot.download_file(file_info.file_path, photo_bytes)

        product_data = await AIService.recognize_product_from_image(photo_bytes.getvalue())
        
        if not product_data or not product_data.get("name"):
            raise ValueError("Не удалось распознать. Попробуй еще раз.")

        user_id = message.from_user.id
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
                fiber=float(product_data.get("fiber", 0)), # SAVE FIBER
                price=0.0,
                quantity=1.0,
                weight_g=float(product_data.get("weight_g", 0)) if product_data.get("weight_g") else None
            )
            session.add(product)
            await session.commit()
            
        builder = InlineKeyboardBuilder()
        builder.button(text="➕ Добавить еще", callback_data="fridge_add:label")
        builder.button(text="🔙 В холодильник", callback_data="menu_fridge")
        builder.adjust(1)

        await status_msg.edit_text(
            f"✅ <b>Добавлено:</b> {product_data['name']}\n"
            f"🔥 {product_data.get('calories')} ккал\n"
            f"🥬 {product_data.get('fiber', 0)}г клетчатки",
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка: {e}")


@router.message(FridgeStates.waiting_for_dish_photo, F.photo)
async def process_fridge_dish(message: types.Message, bot: Bot, state: FSMContext) -> None:
    from services.photo_queue import PhotoQueueManager
    await PhotoQueueManager.add_item(
        user_id=message.from_user.id,
        message=message,
        bot=bot,
        state=state,
        processing_func=process_single_dish,
        file_id=message.photo[-1].file_id
    )

async def process_single_dish(message: types.Message, bot: Bot, state: FSMContext, file_id: str) -> None:
    status_msg = await message.answer("⏳ Анализирую блюдо...")
    try:
        file_info = await bot.get_file(file_id)
        photo_bytes = io.BytesIO()
        await bot.download_file(file_info.file_path, photo_bytes)

        product_data = await AIService.recognize_product_from_image(photo_bytes.getvalue())
        
        if not product_data or not product_data.get("name"):
            raise ValueError("Не удалось распознать блюдо.")

        user_id = message.from_user.id
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
                fiber=float(product_data.get("fiber", 0)), # SAVE FIBER
                price=0.0,
                quantity=1.0, 
                weight_g=float(product_data.get("weight_g", 0)) if product_data.get("weight_g") else None
            )
            session.add(product)
            await session.commit()

        builder = InlineKeyboardBuilder()
        builder.button(text="➕ Добавить еще", callback_data="fridge_add:dish")
        builder.button(text="🔙 В холодильник", callback_data="menu_fridge")
        builder.adjust(1)
        
        await status_msg.edit_text(
            f"✅ <b>Готовое блюдо добавлено:</b>\n{product_data['name']}\n"
            f"🔥 {product_data.get('calories')} ккал\n"
            f"🥬 {product_data.get('fiber', 0)}г клетчатки",
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка: {e}")


@router.message(FridgeStates.waiting_for_consume_grams)
async def process_consume_grams(message: types.Message, state: FSMContext) -> None:
    data = await state.get_data()
    product_id = data.get("product_id")
    page = data.get("page", 0)
    
    try:
        amount = float(message.text.replace(",", "."))
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите положительное число (например: 50 или 100.5)")
        return
    
    await state.clear()
    
    from types import SimpleNamespace
    mock_callback = SimpleNamespace(
        from_user=message.from_user,
        message=message,
        answer=lambda text, show_alert=False: message.answer(text)
    )
    
    await consume_product(mock_callback, product_id, page, amount=amount, unit="grams")

@router.message(FridgeStates.waiting_for_consume_pieces)
async def process_consume_pieces(message: types.Message, state: FSMContext) -> None:
    data = await state.get_data()
    product_id = data.get("product_id")
    page = data.get("page", 0)
    
    try:
        amount = float(message.text.replace(",", "."))
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите положительное число (например: 1 или 0.5)")
        return
    
    await state.clear()
    
    from types import SimpleNamespace
    mock_callback = SimpleNamespace(
        from_user=message.from_user,
        message=message,
        answer=lambda text, show_alert=False: message.answer(text)
    )
    
    await consume_product(mock_callback, product_id, page, amount=amount, unit="qty")



