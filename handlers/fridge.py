"""
Module for fridge management handlers.

Contains handlers for:
- Viewing fridge summary and product list
- Product detail view with pagination
- Consuming and deleting products
"""
import logging
import math
from datetime import datetime

from aiogram import F, Router, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, select

from database.base import get_db
from database.models import ConsumptionLog, Product, Receipt

router = Router()
logger = logging.getLogger(__name__)

PAGE_SIZE: int = 10

# --- Level 2.1: Summary ---
@router.callback_query(F.data == "menu_fridge")
async def show_fridge_summary(callback: types.CallbackQuery) -> None:
    """
    Show fridge summary with total items and recently added products.

    Args:
        callback: Telegram callback query
    """
    user_id = callback.from_user.id

    async for session in get_db():
        # Get total items
        total_items = await session.scalar(
            select(func.count())
            .select_from(Product)
            .join(Receipt)
            .where(Receipt.user_id == user_id)
        ) or 0

        # Get expiring items (mock logic for now, assuming 7 days from receipt date if not set)
        # In real app, we would have expiration_date column.
        # For now, let's just show latest items as "Fresh"

        latest_stmt = (
            select(Product)
            .join(Receipt)
            .where(Receipt.user_id == user_id)
            .order_by(Product.id.desc())
            .limit(3)
        )
        latest_products = (await session.execute(latest_stmt)).scalars().all()

    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Список продуктов", callback_data="fridge_list:0")
    builder.button(text="🔍 Поиск", callback_data="fridge_search") # Placeholder
    builder.button(text="🔙 Назад", callback_data="main_menu")
    builder.adjust(1, 2)

    latest_text = "\n".join([f"▫️ {p.name}" for p in latest_products]) if latest_products else "Пусто"

    # Image path for empty fridge
    empty_photo_path = types.FSInputFile("FoodFlow/assets/empty_fridge.png")

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
    """
    Show paginated list of products in fridge.

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
            .join(Receipt)
            .where(Receipt.user_id == user_id)
        ) or 0

        if total_items == 0:
            await callback.answer("Холодильник пуст!", show_alert=True)
            return

        total_pages = math.ceil(total_items / PAGE_SIZE)
        page = max(0, min(page, total_pages - 1))

        stmt = (
            select(Product)
            .join(Receipt)
            .where(Receipt.user_id == user_id)
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
    """
    Handle no-op callbacks (e.g., page number display button).

    Args:
        callback: Telegram callback query
    """
    await callback.answer()

# --- Level 2.3: Item Detail ---
@router.callback_query(F.data.startswith("fridge_item:"))
async def show_item_detail(callback: types.CallbackQuery):
    """
    Show product detail view with pagination support.

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
        product = await session.get(Product, product_id)
        if not product:
            await callback.answer("Товар не найден", show_alert=True)
            # Refresh list with saved page
            callback.data = f"fridge_list:{page}"
            await show_fridge_list(callback)
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
        builder.button(text="🔙 Назад к списку", callback_data=f"fridge_list:{page}")
        builder.adjust(1)

        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        await callback.answer()

# --- Actions ---
@router.callback_query(F.data.startswith("fridge_eat:"))
async def eat_product(callback: types.CallbackQuery) -> None:
    """
    Mark product as consumed (decrease quantity by 1) and refresh the view.

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
        product = await session.get(Product, product_id)
        if not product:
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
            callback.data = f"fridge_item:{product_id}:{page}"
            await show_item_detail(callback)
        else:
            # Return to list on the same page
            callback.data = f"fridge_list:{page}"
            await show_fridge_list(callback)

@router.callback_query(F.data.startswith("fridge_del:"))
async def delete_product(callback: types.CallbackQuery):
    """
    Delete product completely and return to list.

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
        product = await session.get(Product, product_id)
        if product:
            await session.delete(product)
            await session.commit()
            await callback.answer("🗑️ Товар удален", show_alert=True)

    # Return to list on the same page
    callback.data = f"fridge_list:{page}"
    await show_fridge_list(callback)

