"""Module for user settings management handlers.

Contains:
- SettingsStates: FSM states for settings editing flow
- show_settings: Display current user settings
- start_edit_goals: Initiate editing nutrition goals
- set_calories: Set calorie goal
- set_protein: Set protein goal
- set_fat: Set fat goal
- set_carbs: Set carbs goal and save all goals
- start_edit_allergies: Initiate editing allergies/exclusions
- set_allergies: Save allergies/exclusions
"""
from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from database.base import get_db
from database.models import UserSettings
from services.nutrition_calculator import NutritionCalculator

router = Router()


class SettingsStates(StatesGroup):
    """FSM states for settings editing flow."""

    waiting_for_calories = State()
    waiting_for_protein = State()
    waiting_for_fat = State()
    waiting_for_carbs = State()
    waiting_for_allergies = State()


@router.callback_query(F.data == "menu_settings")
async def show_settings(callback: types.CallbackQuery) -> None:
    """Display current user settings.

    Shows nutrition goals (calories, protein, fat, carbs) and allergies/exclusions.

    Args:
        callback: Telegram callback query

    Returns:
        None

    """
    user_id: int = callback.from_user.id

    async for session in get_db():
        stmt = select(UserSettings).where(UserSettings.user_id == user_id)
        settings = (await session.execute(stmt)).scalar_one_or_none()

        if not settings:
            # Create default settings
            settings = UserSettings(user_id=user_id)
            session.add(settings)
            await session.commit()
            await session.refresh(settings)

        text = (
            "⚙️ <b>Настройки профиля</b>\n\n"
        )

        # Add profile info if initialized
        if settings.is_initialized:
            gender_text = "👨 Мужской" if settings.gender == "male" else "👩 Женский"
            goal_text = {
                "lose_weight": "📉 Похудеть",
                "maintain": "⚖️ Не толстеть",
                "healthy": "🥗 Здоровое питание",
                "gain_mass": "💪 Набрать массу",
            }.get(settings.goal, "🥗 Здоровое питание")

            text += (
                "👤 <b>Профиль:</b>\n"
                f"{gender_text}\n"
                f"📏 Рост: <b>{settings.height}</b> см\n"
                f"⚖️ Вес: <b>{settings.weight}</b> кг\n"
                f"{goal_text}\n\n"
            )

        text += (
            "🎯 <b>Цели КБЖУ:</b>\n"
            f"🔥 Калории: <b>{settings.calorie_goal}</b> ккал\n"
            f"🥩 Белки: <b>{settings.protein_goal}</b> г\n"
            f"🥑 Жиры: <b>{settings.fat_goal}</b> г\n"
            f"🍞 Углеводы: <b>{settings.carb_goal}</b> г\n\n"
            f"🚫 <b>Аллергии/Исключения:</b>\n"
            f"{settings.allergies or 'Нет'}\n\n"
            f"📊 <b>Время дневной сводки:</b> {getattr(settings, 'summary_time', '21:00')}\n"
            f"⏰ <b>Напоминание о весе:</b> {getattr(settings, 'reminder_time', '09:00')}"
        )

        builder = InlineKeyboardBuilder()
        builder.button(text="✏️ Изменить профиль", callback_data="settings_edit_profile")
        builder.button(text="🎯 Изменить цели КБЖУ", callback_data="settings_edit_goals")
        builder.button(text="🚫 Изменить аллергии", callback_data="settings_edit_allergies")
        builder.button(text="🕐 Время сводки", callback_data="settings_edit_summary_time")
        builder.button(text="⏰ Время напоминания", callback_data="settings_edit_reminder_time")
        builder.button(text="🔙 Назад", callback_data="main_menu")
        builder.adjust(1, 1, 1, 2, 1)

        # Image path
        photo_path = types.FSInputFile("assets/main_menu.png")

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
                await callback.message.delete()
                await callback.message.answer_photo(
                    photo=photo_path,
                    caption=text,
                    reply_markup=builder.as_markup(),
                    parse_mode="HTML"
                )
        await callback.answer()

@router.callback_query(F.data == "settings_edit_goals")
async def start_edit_goals(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Initiate editing nutrition goals with recommendations."""
    user_id = callback.from_user.id
    
    async for session in get_db():
        stmt = select(UserSettings).where(UserSettings.user_id == user_id)
        settings = (await session.execute(stmt)).scalar_one_or_none()
        
        if not settings:
            await callback.answer("Профиль не найден", show_alert=True)
            return

        # Calculate recommendations based on current profile
        targets = NutritionCalculator.calculate_targets(
            gender=settings.gender or "male",
            weight=settings.weight or 70,
            height=settings.height or 170,
            age=settings.age or 30,
            goal=settings.goal or "healthy"
        )
        
        # Save pending targets
        await state.update_data(pending_targets=targets)
        await state.update_data(current_settings_weight=settings.weight) # helpful for macros
        await state.update_data(current_settings_goal=settings.goal)
        
        # Build UI
        builder = InlineKeyboardBuilder()
        builder.button(text="✅ Принять рекомендованные", callback_data="settings_goals:accept")
        builder.button(text="✏️ Ввести свои калории", callback_data="settings_goals:manual")
        builder.button(text="🔙 Отмена", callback_data="menu_settings")
        builder.adjust(1)

        text = (
            "🎯 <b>Редактирование целей КБЖУ</b>\n\n"
            f"Текущая цель: <b>{settings.calorie_goal}</b> ккал\n"
            f"Рекомендуемая: <b>{targets['calories']}</b> ккал\n\n"
            f"<i>Рекомендация рассчитана для ваших параметров ({settings.weight}кг, {settings.age} лет).</i>\n\n"
            "Вы можете принять расчет или настроить вручную."
        )

        try:
            await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        except Exception:
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        await callback.answer()


@router.callback_query(F.data == "settings_goals:accept")
async def accept_recommended_goals(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Save recommended goals."""
    data = await state.get_data()
    targets = data.get("pending_targets")
    
    if not targets:
        await callback.answer("Ошибка данных", show_alert=True)
        return
        
    async for session in get_db():
        stmt = select(UserSettings).where(UserSettings.user_id == callback.from_user.id)
        settings = (await session.execute(stmt)).scalar_one_or_none()
        
        if settings:
            settings.calorie_goal = targets["calories"]
            settings.protein_goal = targets["protein"]
            settings.fat_goal = targets["fat"]
            settings.carb_goal = targets["carbs"]
            settings.fiber_goal = targets.get("fiber", 30)
            await session.commit()
            
    await state.clear()
    await show_settings(callback) # Return to settings menu


@router.callback_query(F.data == "settings_goals:manual")
async def start_manual_goals(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Start manual calorie input."""
    await state.set_state(SettingsStates.waiting_for_calories)
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Отмена", callback_data="menu_settings")

    edit_text = (
        "✏️ <b>Ввод своей нормы</b>\n\n"
        "Введите вашу дневную норму <b>калорий</b> (числом, например 2000):\n"
        "<i>Я автоматически пересчитаю БЖУ под вашу цель.</i>"
    )

    try:
        await callback.message.edit_text(edit_text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        await callback.message.delete()
        await callback.message.answer(edit_text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.message(SettingsStates.waiting_for_calories)
async def set_calories(message: types.Message, state: FSMContext) -> None:
    """Set calorie goal and auto-calculate macros."""
    try:
        calories: int = int(message.text)
        if calories < 500 or calories > 10000:
             await message.answer("Пожалуйста, введите разумное число (500-10000).")
             return

        # Retrieve context for macro calc
        data = await state.get_data()
        
        # If we came from settings menu directly without cache (unlikely but possible), fetch defaults
        weight = data.get("current_settings_weight", 70)
        goal = data.get("current_settings_goal", "healthy")
        
        # If not in state, try DB fallback
        if not weight or not goal:
             async for session in get_db():
                stmt = select(UserSettings).where(UserSettings.user_id == message.from_user.id)
                settings = (await session.execute(stmt)).scalar_one_or_none()
                if settings:
                    weight = settings.weight or 70
                    goal = settings.goal or "healthy"
        
        # Calculate macros
        targets = NutritionCalculator.calculate_macros(calories, weight, goal)
        
        # Save to DB immediately (simplification for UX)
        async for session in get_db():
            stmt = select(UserSettings).where(UserSettings.user_id == message.from_user.id)
            settings = (await session.execute(stmt)).scalar_one_or_none()

            if settings:
                settings.calorie_goal = calories
                settings.protein_goal = targets["protein"]
                settings.fat_goal = targets["fat"]
                settings.carb_goal = targets["carbs"]
                settings.fiber_goal = targets.get("fiber", 30)
                await session.commit()
            else:
                 # Should not happen in settings edit, but safety first
                 pass

        await state.clear()

        builder = InlineKeyboardBuilder()
        builder.button(text="🔙 Вернуться в настройки", callback_data="menu_settings")

        await message.answer(
            f"✅ <b>Цели обновлены!</b>\n\n"
            f"🔥 {calories} ккал\n"
            f"🥩 {targets['protein']} / 🥑 {targets['fat']} / 🍞 {targets['carbs']}",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )

    except ValueError:
        await message.answer("Пожалуйста, введите целое число.")

@router.callback_query(F.data == "settings_edit_allergies")
async def start_edit_allergies(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Initiate editing allergies/exclusions.

    Sets FSM state to wait for allergies list from user.

    Args:
        callback: Telegram callback query
        state: FSM context

    Returns:
        None

    """
    await state.set_state(SettingsStates.waiting_for_allergies)
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Отмена", callback_data="menu_settings")

    edit_text = (
        "🚫 <b>Настройка аллергий</b>\n\n"
        "Напишите продукты, которые нужно исключить (через запятую).\n"
        "Например: <i>орехи, молоко, мед</i>\n"
        "Или напишите 'нет', чтобы очистить."
    )

    try:
        await callback.message.edit_text(edit_text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        await callback.message.delete()
        await callback.message.answer(edit_text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()

@router.message(SettingsStates.waiting_for_allergies)
async def set_allergies(message: types.Message, state: FSMContext) -> None:
    """Save allergies/exclusions to user settings.

    Args:
        message: Telegram message with allergies (comma-separated or "нет" to clear)
        state: FSM context

    Returns:
        None

    """
    allergies: str | None = message.text if message.text else None
    if allergies.lower() in ['нет', 'no', '-', 'none']:
        allergies = None

    async for session in get_db():
        stmt = select(UserSettings).where(UserSettings.user_id == message.from_user.id)
        settings = (await session.execute(stmt)).scalar_one_or_none()

        if settings:
            settings.allergies = allergies
            await session.commit()
        else:
            settings = UserSettings(
                user_id=message.from_user.id,
                allergies=allergies
            )
            session.add(settings)
            await session.commit()

    await state.clear()

    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Вернуться в настройки", callback_data="menu_settings")

    await message.answer("✅ Список исключений обновлен!", reply_markup=builder.as_markup())


@router.callback_query(F.data == "settings_edit_profile")
async def edit_profile(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Start profile editing (onboarding flow).

    Args:
        callback: Telegram callback query
        state: FSM context

    Returns:
        None

    """
    from handlers.onboarding import start_onboarding

    # Reset is_initialized to trigger onboarding
    user_id: int = callback.from_user.id
    async for session in get_db():
        stmt = select(UserSettings).where(UserSettings.user_id == user_id)
        settings = (await session.execute(stmt)).scalar_one_or_none()
        if settings:
            settings.is_initialized = False
            await session.commit()
            settings.is_initialized = False
            await session.commit()

    # Start onboarding
    await start_onboarding(callback.message, state)


@router.callback_query(F.data == "settings_edit_summary_time")
async def edit_summary_time(callback: types.CallbackQuery) -> None:
    """Show time selection for daily summary."""
    builder = InlineKeyboardBuilder()
    
    # Popular times as buttons
    times = ["18:00", "19:00", "20:00", "21:00", "22:00", "23:00"]
    for t in times:
        builder.button(text=f"🕐 {t}", callback_data=f"set_summary_time:{t}")
    builder.button(text="🔙 Назад", callback_data="menu_settings")
    builder.adjust(3, 3, 1)
    
    text = (
        "🕐 <b>Выберите время дневной сводки:</b>\n\n"
        "В это время вам придёт отчёт о питании за день."
    )
    
    # Handle both photo and text messages
    try:
        # Try to edit caption (for photo messages)
        await callback.message.edit_caption(
            caption=text,
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
    except Exception:
        try:
            # Try to edit text (for text messages)
            await callback.message.edit_text(
                text,
                parse_mode="HTML",
                reply_markup=builder.as_markup()
            )
        except Exception:
            # Delete and send new
            await callback.message.delete()
            await callback.message.answer(
                text,
                parse_mode="HTML",
                reply_markup=builder.as_markup()
            )
    await callback.answer()


@router.callback_query(F.data.startswith("set_summary_time:"))
async def save_summary_time(callback: types.CallbackQuery) -> None:
    """Save selected summary time."""
    new_time = callback.data.split(":")[1] + ":" + callback.data.split(":")[2]
    user_id = callback.from_user.id
    
    async for session in get_db():
        stmt = select(UserSettings).where(UserSettings.user_id == user_id)
        settings = (await session.execute(stmt)).scalar_one_or_none()
        
        if settings:
            settings.summary_time = new_time
            await session.commit()
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Вернуться в настройки", callback_data="menu_settings")
    
    text = (
        f"✅ Время дневной сводки установлено: <b>{new_time}</b>\n\n"
        "Теперь отчёт будет приходить в это время каждый день."
    )
    
    try:
        await callback.message.edit_caption(
            caption=text,
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
    except Exception:
        try:
            await callback.message.edit_text(
                text,
                parse_mode="HTML",
                reply_markup=builder.as_markup()
            )
        except Exception:
            await callback.message.delete()
            await callback.message.answer(
                text,
                parse_mode="HTML",
                reply_markup=builder.as_markup()
            )
    await callback.answer()


@router.callback_query(F.data == "settings_edit_reminder_time")
async def edit_reminder_time(callback: types.CallbackQuery) -> None:
    """Show time selection for weight reminder."""
    builder = InlineKeyboardBuilder()
    times = ["07:00", "08:00", "09:00", "10:00", "11:00", "12:00"]
    for time in times:
        builder.button(text=f"⏰ {time}", callback_data=f"set_reminder_time:{time}")
    builder.button(text="🔙 Назад", callback_data="menu_settings")
    builder.adjust(3, 3, 1)
    
    text = (
        "⏰ <b>Время напоминания о весе</b>\n\n"
        "В это время бот будет напоминать записать вес.\n\n"
        "Выберите удобное время:"
    )
    
    try:
        await callback.message.edit_caption(
            caption=text,
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
    except Exception:
        try:
            await callback.message.edit_text(
                text,
                parse_mode="HTML",
                reply_markup=builder.as_markup()
            )
        except Exception:
            await callback.message.delete()
            await callback.message.answer(
                text,
                parse_mode="HTML",
                reply_markup=builder.as_markup()
            )
    await callback.answer()


@router.callback_query(F.data.startswith("set_reminder_time:"))
async def save_reminder_time(callback: types.CallbackQuery) -> None:
    """Save the selected reminder time."""
    new_time = callback.data.split(":")[1] + ":00"
    user_id = callback.from_user.id
    
    async for session in get_db():
        stmt = select(UserSettings).where(UserSettings.user_id == user_id)
        settings = (await session.execute(stmt)).scalar_one_or_none()
        
        if settings:
            settings.reminder_time = new_time
            await session.commit()
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Вернуться в настройки", callback_data="menu_settings")
    
    text = (
        f"✅ Время напоминания о весе установлено: <b>{new_time}</b>\n\n"
        "Теперь бот будет напоминать записать вес в это время."
    )
    
    try:
        await callback.message.edit_caption(
            caption=text,
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
    except Exception:
        try:
            await callback.message.edit_text(
                text,
                parse_mode="HTML",
                reply_markup=builder.as_markup()
            )
        except Exception:
            await callback.message.delete()
            await callback.message.answer(
                text,
                parse_mode="HTML",
                reply_markup=builder.as_markup()
            )
    await callback.answer()

