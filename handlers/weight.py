"""Module for weight tracking handlers.

Contains:
- WeightStates: FSM states for weight input
- show_weight_menu: Display weight tracking options
- start_weight_input: Initiate weight recording
- save_weight: Save weight to database
"""
from datetime import datetime

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from database.base import get_db
from database.models import UserSettings, WeightLog

router = Router()


class WeightStates(StatesGroup):
    """FSM states for weight tracking."""
    waiting_for_weight = State()
    waiting_for_morning_weight = State()


@router.callback_query(F.data == "menu_weight")
async def show_weight_menu(callback: types.CallbackQuery) -> None:
    """Show weight tracking menu with current weight and history."""
    user_id = callback.from_user.id
    
    # Clear state if entering from menu, to reset any stale states
    # But wait, checking logic above: usually menus don't clear unless explicit.
    # Actually, standard behavior: just show menu.
    
    async for session in get_db():
        # Get current weight from settings
        settings_stmt = select(UserSettings).where(UserSettings.user_id == user_id)
        settings = (await session.execute(settings_stmt)).scalar_one_or_none()
        
        # Get last 5 weight entries
        logs_stmt = (
            select(WeightLog)
            .where(WeightLog.user_id == user_id)
            .order_by(WeightLog.recorded_at.desc())
            .limit(5)
        )
        logs = (await session.execute(logs_stmt)).scalars().all()

        current_weight = settings.weight if settings else "?"
        
        text = f"⚖️ <b>Отслеживание веса</b>\n\n"
        text += f"📊 Текущий вес: <b>{current_weight} кг</b>\n\n"
        
        if logs:
            text += "📈 <b>История:</b>\n"
            for log in logs:
                date_str = log.recorded_at.strftime("%d.%m")
                text += f"  • {date_str}: {log.weight} кг\n"
        else:
            text += "📈 История пуста. Начни записывать вес!\n"

        builder = InlineKeyboardBuilder()
        builder.button(text="✏️ Записать вес", callback_data="weight_input")
        builder.button(text="🔙 Назад", callback_data="main_menu")
        builder.adjust(1)

        try:
            await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        except Exception:
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        await callback.answer()


@router.callback_query(F.data == "weight_input")
async def start_weight_input(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Start weight input flow."""
    await state.set_state(WeightStates.waiting_for_weight)
    
    user_id = callback.from_user.id
    current_weight = None

    async for session in get_db():
        settings_stmt = select(UserSettings).where(UserSettings.user_id == user_id)
        settings = (await session.execute(settings_stmt)).scalar_one_or_none()
        if settings and settings.weight:
            current_weight = settings.weight

    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Отмена", callback_data="menu_weight")

    prompt_suffix = "(например: 72.5)"
    if current_weight:
        prompt_suffix = f"(прошлый: {current_weight})"

    text = (
        "✏️ <b>Запись веса</b>\n\n"
        f"Введите ваш текущий вес в килограммах {prompt_suffix}:"
    )

    try:
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.message(WeightStates.waiting_for_weight)
@router.message(WeightStates.waiting_for_morning_weight)
async def save_weight(message: types.Message, state: FSMContext) -> None:
    """Save weight to database."""
    try:
        weight = float(message.text.replace(",", ".")) if message.text else 0.0
        if weight < 20 or weight > 300:
            await message.answer("Пожалуйста, введите корректный вес (20-300 кг):")
            return

        async for session in get_db():
            # Save to weight log
            log = WeightLog(
                user_id=message.from_user.id,
                weight=weight,
                recorded_at=datetime.now()
            )
            session.add(log)
            
            # Update current weight in settings
            settings_stmt = select(UserSettings).where(UserSettings.user_id == message.from_user.id)
            settings = (await session.execute(settings_stmt)).scalar_one_or_none()
            if settings:
                settings.weight = weight
            
            await session.commit()

        await state.clear()

        builder = InlineKeyboardBuilder()
        builder.button(text="⚖️ К весу", callback_data="menu_weight")
        builder.button(text="🏠 В меню", callback_data="main_menu")
        builder.adjust(2)

        await message.answer(
            f"✅ Вес <b>{weight} кг</b> записан!",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )

    except ValueError:
        builder = InlineKeyboardBuilder()
        builder.button(text="❌ Отмена (Я хочу записать еду)", callback_data="menu_weight") # Redirect to weight menu or cancel? menu_weight acts as back/cancel here effectively or we can clear state.
        # Actually standard practice is usually 'cancel' -> clears state.
        # But 'menu_weight' button above (line 93) was 'Back'.
        # Let's use a clear 'cancel' that clears state and goes to main menu or just clears.
        builder.button(text="🔙 Отмена", callback_data="main_menu") 
        
        await message.answer(
            "⚠️ <b>Ожидается вес тела (кг)</b>\n\n"
            "Вы ввели текст, но я жду число (например: 75.5).\n"
            "Если вы хотели записать съеденное — нажмите кнопку ниже.",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
