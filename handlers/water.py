"""Module for handling water intake logging."""
import logging
from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.base import get_db
from database.models import WaterLog

logger = logging.getLogger(__name__)
router = Router()

@router.callback_query(F.data == "menu_water")
async def show_water_menu(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Show options for adding water."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🥤 +200 мл", callback_data="add_water:200")
    builder.button(text="🥛 +250 мл", callback_data="add_water:250")
    builder.button(text="🍼 +500 мл", callback_data="add_water:500")
    builder.button(text="💧 +1000 мл", callback_data="add_water:1000")
    builder.button(text="🔙 Назад", callback_data="main_menu")
    builder.adjust(2, 2, 1)

    text = (
        "💧 <b>Добавление воды</b>\n\n"
        "Сколько воды ты сейчас выпил?"
    )

    try:
         await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
         await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("add_water:"))
async def process_add_water(callback: types.CallbackQuery, state: FSMContext, user_tier: str = "free") -> None:
    """Process quick add water buttons."""
    amount_ml = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    async for session in get_db():
        log = WaterLog(
            user_id=user_id,
            amount_ml=amount_ml
        )
        session.add(log)
        await session.commit()

    await callback.answer(f"✅ Добавлено {amount_ml} мл воды!", show_alert=True)
    
    # Return to main menu immediately to show updated dashboard
    from handlers.menu import show_main_menu
    await show_main_menu(callback.message, callback.from_user.first_name, user_id, user_tier)
