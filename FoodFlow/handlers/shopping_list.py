from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from FoodFlow.database.base import get_db
from FoodFlow.database.models import ShoppingListItem

router = Router()

class ShoppingListStates(StatesGroup):
    waiting_for_item_name = State()

@router.callback_query(F.data == "menu_shopping_list")
async def show_shopping_list(callback: types.CallbackQuery):
    user_id = callback.from_user.id

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

        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        await callback.answer()

@router.callback_query(F.data == "shop_add")
async def start_add_item(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(ShoppingListStates.waiting_for_item_name)
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Отмена", callback_data="menu_shopping_list")

    await callback.message.edit_text(
        "➕ <b>Добавление товара</b>\n\n"
        "Напиши название товара (или несколько через запятую):",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(ShoppingListStates.waiting_for_item_name)
async def add_item(message: types.Message, state: FSMContext):
    raw_text = message.text
    items = [i.strip() for i in raw_text.split(',') if i.strip()]

    async for session in get_db():
        for item_name in items:
            new_item = ShoppingListItem(
                user_id=message.from_user.id,
                product_name=item_name
            )
            session.add(new_item)
        await session.commit()

    await state.clear()

    # Return to list
    # Since we are in message handler, we need to send a new message or just confirm
    # Let's try to show the list again by calling the handler logic?
    # Or just a confirmation message with button.

    builder = InlineKeyboardBuilder()
    builder.button(text="📝 К списку покупок", callback_data="menu_shopping_list")

    await message.answer(f"✅ Добавлено {len(items)} товаров!", reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("shop_buy:"))
async def mark_bought(callback: types.CallbackQuery):
    item_id = int(callback.data.split(":")[1])

    async for session in get_db():
        item = await session.get(ShoppingListItem, item_id)
        if item and item.user_id == callback.from_user.id:
            item.is_bought = True
            await session.commit()

    await show_shopping_list(callback)

@router.callback_query(F.data.startswith("shop_unbuy:"))
async def mark_unbought(callback: types.CallbackQuery):
    item_id = int(callback.data.split(":")[1])

    async for session in get_db():
        item = await session.get(ShoppingListItem, item_id)
        if item and item.user_id == callback.from_user.id:
            item.is_bought = False
            await session.commit()

    await show_shopping_list(callback)

@router.callback_query(F.data == "shop_clear_bought")
async def clear_bought(callback: types.CallbackQuery):
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
