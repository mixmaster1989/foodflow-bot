"""Module for shopping list management handlers.

Contains:
- ShoppingListStates: FSM states for shopping list operations
- show_shopping_list: Display shopping list with active and bought items
- start_add_item: Initiate adding new item to shopping list
- add_item: Add items from user message to shopping list
- mark_bought: Mark item as bought
- mark_unbought: Mark item as not bought
- clear_bought: Delete all bought items
"""
from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from database.base import get_db
from database.models import Product, ShoppingListItem, UserSettings
from services.consultant import ConsultantService
from sqlalchemy import select

router = Router()


class ShoppingListStates(StatesGroup):
    """FSM states for shopping list operations."""

    waiting_for_item_name = State()


@router.callback_query(F.data == "menu_shopping_list")
async def show_shopping_list(callback: types.CallbackQuery) -> None:
    """Display shopping list with active and bought items.

    Shows all shopping list items grouped by status (active/bought)
    with buttons to mark items as bought/unbought.

    Args:
        callback: Telegram callback query

    Returns:
        None

    """
    user_id: int = callback.from_user.id

    async for session in get_db():
        stmt = select(ShoppingListItem).where(ShoppingListItem.user_id == user_id).order_by(ShoppingListItem.is_bought, ShoppingListItem.created_at)
        items = (await session.execute(stmt)).scalars().all()

        builder = InlineKeyboardBuilder()

        # Active items
        active_items = [i for i in items if not i.is_bought]
        bought_items = [i for i in items if i.is_bought]

        text = "📝 <b>Список покупок</b>\n\n"

        if not items:
            text += "Список пуст. Добавь что-нибудь!"
        else:
            if active_items:
                text += "<b>Нужно купить:</b>\n"
                for item in active_items:
                    builder.button(text=f"⬜ {item.product_name}", callback_data=f"shop_buy:{item.id}")

            if bought_items:
                text += "\n<b>Куплено:</b>\n"
                for item in bought_items:
                    builder.button(text=f"✅ {item.product_name}", callback_data=f"shop_unbuy:{item.id}")

        builder.adjust(1)

        # Action buttons
        builder.row(
            types.InlineKeyboardButton(text="➕ Добавить", callback_data="shop_add"),
            types.InlineKeyboardButton(text="🗑️ Очистить купленное", callback_data="shop_clear_bought")
        )
        builder.row(types.InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu"))

        # Image path
        photo_path = types.FSInputFile("assets/shopping_list.png")

        # Try to edit media (photo), if fails try edit_text, if fails delete and send new
        try:
            await callback.message.edit_media(
                media=types.InputMediaPhoto(media=photo_path, caption=text, parse_mode="HTML"),
                reply_markup=builder.as_markup()
            )
        except Exception:
            try:
                await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
            except Exception:
                # If previous message was photo, we can't edit_text it, so delete and send new
                await callback.message.delete()
                await callback.message.answer_photo(
                    photo=photo_path,
                    caption=text,
                    reply_markup=builder.as_markup(),
                    parse_mode="HTML"
                )
        await callback.answer()

@router.callback_query(F.data == "shop_add")
async def start_add_item(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Initiate adding new item to shopping list.

    Sets FSM state to wait for item name from user.

    Args:
        callback: Telegram callback query
        state: FSM context

    Returns:
        None

    """
    await state.set_state(ShoppingListStates.waiting_for_item_name)
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Отмена", callback_data="menu_shopping_list")

    add_text = (
        "➕ <b>Добавление товара</b>\n\n"
        "Напиши название товара (или несколько через запятую):"
    )

    try:
        await callback.message.edit_text(add_text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        await callback.message.delete()
        await callback.message.answer(add_text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()

@router.message(ShoppingListStates.waiting_for_item_name)
async def add_item(message: types.Message, state: FSMContext) -> None:
    """Add items from user message to shopping list.

    Parses comma-separated item names and creates shopping list items.

    Args:
        message: Telegram message with item names (comma-separated)
        state: FSM context

    Returns:
        None

    """
    raw_text: str = message.text if message.text else ""
    items: list[str] = [i.strip() for i in raw_text.split(',') if i.strip()]

    async for session in get_db():
        for item_name in items:
            new_item = ShoppingListItem(
                user_id=message.from_user.id,
                product_name=item_name
            )
            session.add(new_item)
        await session.commit()

        # Get user settings for consultant
        settings_stmt = select(UserSettings).where(UserSettings.user_id == message.from_user.id)
        settings_result = await session.execute(settings_stmt)
        settings = settings_result.scalar_one_or_none()

        # Show recommendations for each added item
        if settings and settings.is_initialized and items:
            recommendation_texts = []
            for item_name in items:
                # Create temporary Product object for analysis
                temp_product = Product(
                    name=item_name,
                    calories=0.0,
                    protein=0.0,
                    fat=0.0,
                    carbs=0.0,
                    category=None,
                    price=0.0,
                    quantity=1.0
                )
                recommendations = await ConsultantService.analyze_product(
                    temp_product, settings, context="shopping_list"
                )
                warnings = recommendations.get("warnings", [])
                recs = recommendations.get("recommendations", [])
                missing = recommendations.get("missing", [])

                if warnings or recs or missing:
                    item_rec = f"<b>{item_name}:</b>\n"
                    if warnings:
                        item_rec += "\n".join(warnings) + "\n"
                    if recs:
                        item_rec += "\n".join(recs) + "\n"
                    if missing:
                        item_rec += "\n".join(missing)
                    recommendation_texts.append(item_rec)

            if recommendation_texts:
                full_text = "💡 <b>Рекомендации консультанта:</b>\n\n" + "\n\n".join(recommendation_texts)
                await message.answer(full_text, parse_mode="HTML")

    await state.clear()

    # Return to list
    # Since we are in message handler, we need to send a new message or just confirm
    # Let's try to show the list again by calling the handler logic?
    # Or just a confirmation message with button.

    builder = InlineKeyboardBuilder()
    builder.button(text="📝 К списку покупок", callback_data="menu_shopping_list")

    await message.answer(f"✅ Добавлено {len(items)} товаров!", reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("shop_buy:"))
async def mark_bought(callback: types.CallbackQuery) -> None:
    """Mark shopping list item as bought.

    Args:
        callback: Telegram callback query with data format "shop_buy:{item_id}"

    Returns:
        None

    """
    item_id: int = int(callback.data.split(":")[1])

    async for session in get_db():
        item = await session.get(ShoppingListItem, item_id)
        if item and item.user_id == callback.from_user.id:
            item.is_bought = True
            await session.commit()

    await show_shopping_list(callback)

@router.callback_query(F.data.startswith("shop_unbuy:"))
async def mark_unbought(callback: types.CallbackQuery) -> None:
    """Mark shopping list item as not bought.

    Args:
        callback: Telegram callback query with data format "shop_unbuy:{item_id}"

    Returns:
        None

    """
    item_id: int = int(callback.data.split(":")[1])

    async for session in get_db():
        item = await session.get(ShoppingListItem, item_id)
        if item and item.user_id == callback.from_user.id:
            item.is_bought = False
            await session.commit()

    await show_shopping_list(callback)

@router.callback_query(F.data == "shop_clear_bought")
async def clear_bought(callback: types.CallbackQuery) -> None:
    """Delete all bought items from shopping list.

    Args:
        callback: Telegram callback query

    Returns:
        None

    """
    async for session in get_db():
        # Delete all bought items for this user
        # Need to select them first to delete? Or execute delete statement directly.
        # SQLAlchemy delete statement is better.
        from sqlalchemy import delete
        stmt = delete(ShoppingListItem).where(
            ShoppingListItem.user_id == callback.from_user.id,
            ShoppingListItem.is_bought  # noqa: E712
        )
        await session.execute(stmt)
        await session.commit()

    await callback.answer("🗑️ Купленные товары удалены")
    await show_shopping_list(callback)
