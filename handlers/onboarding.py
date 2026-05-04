"""Module for user onboarding (initial setup).

Contains:
- OnboardingStates: FSM states for onboarding flow
- start_onboarding: Start onboarding process
- handle_source_selection: Handle acquisition source survey
- handle_gender_selection: Handle gender selection
- handle_height_input: Handle height input
- handle_weight_input: Handle weight input
- handle_goal_selection: Handle goal selection
- finish_onboarding: Save data and complete onboarding
"""
import io
import json
import logging

from aiogram import Bot, F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import and_, func, select

from database.base import get_db
from database.models import Product, UserSettings, User, Subscription, UserFeedback
from handlers.menu import show_main_menu
from services.consultant import ConsultantService
from services.nutrition_calculator import NutritionCalculator
from services.photo_queue import PhotoQueueManager

logger = logging.getLogger(__name__)

router = Router()

# Acquisition source options
ACQUISITION_SOURCES = {
    "tg_ads": "📢 Реклама в Телеграм",
    "friend": "👤 Рекомендация друга",
    "social": "📱 Соцсети (Inst/VK/YT)",
    "search": "🔍 Поиск в интернете",
    "blogger": "🗣️ Блогер / инфлюенсер",
    "herbalife": "🌿 Мероприятие Herbalife",
    "other": "🔗 Другое",
}


class OnboardingStates(StatesGroup):
    """FSM states for onboarding flow."""

    waiting_for_source = State()   # Acquisition source survey
    waiting_for_gender = State()
    waiting_for_age = State()
    waiting_for_height = State()
    waiting_for_weight = State()
    waiting_for_goal = State()
    waiting_for_calorie_confirmation = State()
    waiting_for_manual_calories = State()
    initializing_fridge = State()


async def start_onboarding(message: types.Message, state: FSMContext) -> None:
    """Start onboarding process for new users."""
    user_id: int = message.from_user.id

    async for session in get_db():
        stmt = select(UserSettings).where(UserSettings.user_id == user_id)
        settings = (await session.execute(stmt)).scalar_one_or_none()

        # If user already initialized, show main menu
        if settings and settings.is_initialized:
            await show_main_menu(message, message.from_user.first_name, message.from_user.id)
            return

        # Check if we already have ad_campaign in UserFeedback
        fb_stmt = select(UserFeedback).where(
            and_(
                UserFeedback.user_id == user_id,
                UserFeedback.feedback_type == "ad_campaign"
            )
        )
        fb = (await session.execute(fb_stmt)).scalar_one_or_none()

        if fb:
            # Skip source survey, go straight to gender
            logger.info(f"User {user_id} has ad_campaign '{fb.answer}', skipping source survey")
            await show_gender_selection(message, state)
        else:
            # Start onboarding with acquisition source survey
            await state.set_state(OnboardingStates.waiting_for_source)

            builder = InlineKeyboardBuilder()
            for key, label in ACQUISITION_SOURCES.items():
                builder.button(text=label, callback_data=f"onboarding_source:{key}")
            builder.adjust(2)

            welcome_text = (
                "👋 <b>Добро пожаловать в FoodFlow!</b>\n\n"
                "Я помогу тебе следить за питанием и управлять продуктами.\n\n"
                "Для начала один вопрос:\n\n"
                "📋 <b>Откуда вы о нас узнали?</b>"
            )

            await message.answer(welcome_text, reply_markup=builder.as_markup(), parse_mode="HTML")


async def show_gender_selection(message: types.Message, state: FSMContext) -> None:
    """Show gender selection screen."""
    await state.set_state(OnboardingStates.waiting_for_gender)

    builder = InlineKeyboardBuilder()
    builder.button(text="👨 Мужской", callback_data="onboarding_gender:male")
    builder.button(text="👩 Женский", callback_data="onboarding_gender:female")
    builder.adjust(2)

    text = (
        "👋 <b>Давай настроим твой профиль!</b>\n\n"
        "Для точного расчета КБЖУ мне нужны твои параметры.\n\n"
        "1️⃣ Выбери свой пол:"
    )

    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")


@router.callback_query(F.data.startswith("onboarding_source:"))
async def handle_source_selection(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Handle acquisition source survey answer.

    Saves enriched user data (username, name, etc.) alongside the chosen source
    to UserFeedback table for marketing analysis.
    """
    source_key = callback.data.split(":")[1]
    source_label = ACQUISITION_SOURCES.get(source_key, source_key)
    user = callback.from_user

    # Save to UserFeedback with enriched profile
    answer_data = json.dumps({
        "source": source_key,
        "source_label": source_label,
        "user_id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "language_code": user.language_code,
        "is_premium": getattr(user, "is_premium", False) or False,
    }, ensure_ascii=False)

    async for session in get_db():
        fb = UserFeedback(
            user_id=user.id,
            feedback_type="acquisition_source",
            answer=answer_data,
        )
        session.add(fb)
        await session.commit()

    logger.info(f"Acquisition source saved: user={user.id} source={source_key}")

    # Transition to gender selection (step 1)
    await state.set_state(OnboardingStates.waiting_for_gender)

    builder = InlineKeyboardBuilder()
    builder.button(text="👨 Мужской", callback_data="onboarding_gender:male")
    builder.button(text="👩 Женский", callback_data="onboarding_gender:female")
    builder.adjust(2)

    text = (
        "<b>✅ Спасибо!</b>\n\n"
        "Теперь мне нужно узнать немного о тебе:\n\n"
        "1️⃣ Выбери свой пол:"
    )

    try:
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        await callback.message.delete()
import asyncio

async def show_ephemeral_warning(message: types.Message, text: str, parse_mode: str = None) -> None:
    """Show a warning message and auto-delete it after 6 seconds, also deleting the user's invalid input."""
    try:
        await message.delete()
    except Exception:
        pass
        
    msg = await message.answer(text, parse_mode=parse_mode)
    
    async def _delete():
        await asyncio.sleep(6)
        try:
            await msg.delete()
        except Exception:
            pass
            
    asyncio.create_task(_delete())


@router.message(OnboardingStates.waiting_for_source)
async def handle_source_fallback(message: types.Message) -> None:
    """Handle text input during source selection."""
    await show_ephemeral_warning(message, "Пожалуйста, воспользуйтесь кнопками выше, чтобы выбрать ответ. 👆")


@router.callback_query(F.data.startswith("onboarding_gender:"))

async def handle_gender_selection(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Handle gender selection."""
    gender = callback.data.split(":")[1]  # "male" or "female"
    await state.update_data(gender=gender)
    await state.set_state(OnboardingStates.waiting_for_age)

    text = (
        "<b>✅ Отлично!</b>\n\n"
        "2️⃣ Теперь напиши свой <b>возраст</b> (полных лет):\n\n"
        "<i>Например: 30</i>"
    )

    try:
        await callback.message.edit_text(text, parse_mode="HTML")
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()


@router.message(OnboardingStates.waiting_for_gender)
async def handle_gender_fallback(message: types.Message) -> None:
    """Handle text input during gender selection."""
    await show_ephemeral_warning(message, "Пожалуйста, воспользуйтесь кнопками выше (👨 или 👩). 👆")


@router.message(OnboardingStates.waiting_for_age)
async def handle_age_input(message: types.Message, state: FSMContext) -> None:
    try:
        age = int(message.text)
        if not (14 <= age <= 100):
            await message.answer("Возраст должен быть от 14 до 100 лет.")
            return

        await state.update_data(age=age)
        await state.set_state(OnboardingStates.waiting_for_height)

        text = (
            "<b>✅ Принято!</b>\n\n"
            "3️⃣ Укажи свой <b>рост</b> (в см):\n\n"
            "<i>Например: 175</i>"
        )
        await message.answer(text, parse_mode="HTML")
    except ValueError:
        await message.answer("Пожалуйста, введите число (например, 30).")

@router.message(OnboardingStates.waiting_for_height)
async def handle_height_input(message: types.Message, state: FSMContext) -> None:
    try:
        height = int(message.text.replace(",", ".").split(".")[0])
        if not (50 <= height <= 250):
            await message.answer("Рост должен быть от 50 до 250 см.")
            return

        await state.update_data(height=height)
        await state.set_state(OnboardingStates.waiting_for_weight)

        text = (
            "<b>✅ Записал.</b>\n\n"
            "4️⃣ И последнее число — твой <b>текущий вес</b> (в кг):\n\n"
            "<i>Например: 75.5</i>"
        )
        await message.answer(text, parse_mode="HTML")
    except ValueError:
        await message.answer("Пожалуйста, введите число (например, 175).")

@router.message(OnboardingStates.waiting_for_weight)
async def handle_weight_input(message: types.Message, state: FSMContext) -> None:
    try:
        weight = float(message.text.replace(",", "."))
        if not (30 <= weight <= 300):
            await message.answer("Вес должен быть от 30 до 300 кг.")
            return

        await state.update_data(weight=weight)
        await state.set_state(OnboardingStates.waiting_for_goal)
        
        data = await state.get_data()
        
        builder = InlineKeyboardBuilder()
        builder.button(text="📉 Похудеть", callback_data="onboarding_goal:lose_weight")
        builder.button(text="⚖️ Не набирать", callback_data="onboarding_goal:maintain")
        builder.button(text="🥗 Здоровое питание", callback_data="onboarding_goal:healthy")
        builder.button(text="💪 Набрать массу", callback_data="onboarding_goal:gain_mass")
        builder.adjust(2)

        text = (
            f"<b>✅ Данные приняты: {data.get('age')} лет, {data.get('height')} см, {weight} кг</b>\n\n"
            "5️⃣ Выбери свою <b>главную цель</b>:"
        )

        await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except ValueError:
        await message.answer("Пожалуйста, введите число (например, 75.5).")


@router.message(OnboardingStates.waiting_for_goal)
async def handle_goal_fallback(message: types.Message) -> None:
    """Handle text input during goal selection."""
    await show_ephemeral_warning(message, "Пожалуйста, выберите цель, нажав на одну из кнопок выше. 👆")


@router.callback_query(F.data.startswith("onboarding_goal:"))
async def handle_goal_selection(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Handle goal selection and finish onboarding.

    Args:
        callback: Telegram callback query with goal data
        state: FSM context

    Returns:
        None

    """
    goal = callback.data.split(":")[1]  # "lose_weight", "maintain", "healthy", "gain_mass"

    # Store goal in state
    await state.update_data(goal=goal)
    data = await state.get_data()

    # Calculate recommendations
    gender = data.get("gender", "male")
    age = data.get("age", 30)
    height = data.get("height", 170)
    weight = data.get("weight", 70)

    targets = NutritionCalculator.calculate_targets(gender, weight, height, age, goal)

    # Store calculated targets in state as "pending"
    await state.update_data(pending_targets=targets)

    await state.set_state(OnboardingStates.waiting_for_calorie_confirmation)

    # Show recommendations
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Принять (авто)", callback_data="onboarding_goals:accept")
    builder.button(text="✏️ Ввести свои калории", callback_data="onboarding_goals:manual")
    builder.button(text="🔙 Назад", callback_data="onboarding_back:to_goal_selection")
    builder.adjust(1)

    goal_names = {
        "lose_weight": "Похудение",
        "maintain": "Поддержание",
        "healthy": "Здоровье",
        "gain_mass": "Набор массы"
    }

    text = (
        f"🎯 <b>Цель: {goal_names.get(goal, 'Здоровье')}</b>\n\n"
        f"Исходя из твоих параметров, я рассчитал рекомендуемые нормы:\n\n"
        f"🔥 <b>Калории: <code>{targets['calories']} ккал</code></b>\n"
        f"🥩 Белки: <code>{targets['protein']} г</code>\n"
        f"🥑 Жиры: <code>{targets['fat']} г</code>\n"
        f"🍞 Углеводы: <code>{targets['carbs']} г</code>\n\n"
        "<b>Согласен с этим расчетом?</b>"
    )

    try:
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "onboarding_goals:accept")
async def handle_goal_accept(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Accept calculated goals and finish."""
    data = await state.get_data()
    targets = data.get("pending_targets")

    if not targets:
        await callback.answer("Ошибка данных, начните заново", show_alert=True)
        return

    await finish_onboarding_process(callback.message, state, targets)
    await callback.answer()


@router.message(OnboardingStates.waiting_for_calorie_confirmation)
async def handle_calorie_confirmation_text(message: types.Message, state: FSMContext) -> None:
    """Handle text input during calorie confirmation (e.g. 'No', 'Too much')."""
    text = message.text.lower()
    
    if any(word in text for word in ["нет", "не", "много", "no", "stop", "угл"]):
        await show_ephemeral_warning(
            message,
            "📍 <b>Я понял, что расчет тебя не устраивает.</b>\n\n"
            "Ты можешь нажать кнопку <b>«✏️ Ввести свои калории»</b> выше, "
            "чтобы задать норму самостоятельно, или нажать <b>«🔙 Назад»</b>, "
            "чтобы изменить свою цель.\n\n"
            "КБЖУ — это всего лишь прогноз, ты всегда можешь его подправить! ✨",
            parse_mode="HTML"
        )
    else:
        await show_ephemeral_warning(
            message,
            "☝️ <b>Пожалуйста, воспользуйтесь кнопками выше</b>, чтобы подтвердить расчет, "
            "ввести свои значения или вернуться назад."
        )


@router.callback_query(F.data == "onboarding_goals:manual")
async def handle_goal_manual_start(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Ask for manual calories."""
    await state.set_state(OnboardingStates.waiting_for_manual_calories)

    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="onboarding_back:goals") # We need to handle this back

    text = (
        "<b>✏️ Ввод своей нормы</b>\n\n"
        "Введите желаемое количество калорий в день (например: <code>1800</code>).\n"
        "Я автоматически пересчитаю БЖУ под твою цель."
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="onboarding_back:calorie_confirmation")
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.message(OnboardingStates.waiting_for_manual_calories)
async def handle_manual_calories_input(message: types.Message, state: FSMContext) -> None:
    """Process manual calories and recalculate macros."""
    try:
        calories = int(message.text)
        if calories < 500 or calories > 10000:
            await message.answer("Пожалуйста, введите разумное число (500-10000).")
            return

        data = await state.get_data()
        weight = data.get("weight", 70)
        goal = data.get("goal", "healthy")

        # Recalculate macros based on NEW calories
        targets = NutritionCalculator.calculate_macros(calories, weight, goal)

        await finish_onboarding_process(message, state, targets)

    except ValueError:
        await message.answer("Пожалуйста, введите целое число.")


async def finish_onboarding_process(message: types.Message, state: FSMContext, targets: dict) -> None:
    """Save all data to DB and show finish screen."""
    data = await state.get_data()
    user_id = message.chat.id # Use chat.id because message.from_user is bot in callbacks

    async for session in get_db():
        stmt = select(UserSettings).where(UserSettings.user_id == user_id)
        settings = (await session.execute(stmt)).scalar_one_or_none()

        gender = data.get("gender", "male")
        age = data.get("age", 30)
        height = data.get("height", 170)
        weight = data.get("weight", 70)
        goal = data.get("goal", "healthy")

        # Calculate water goal
        water_goal = int(weight * 30)
        if goal in ["lose_weight", "gain_mass"]:
            water_goal += 500

        if settings:
            settings.gender = gender
            settings.age = age
            settings.height = height
            settings.weight = weight
            settings.goal = goal
            settings.calorie_goal = targets["calories"]
            settings.protein_goal = targets["protein"]
            settings.fat_goal = targets["fat"]
            settings.carb_goal = targets["carbs"]
            settings.fiber_goal = targets.get("fiber", 30)
            settings.water_goal = water_goal
            settings.is_initialized = True
        else:
            settings = UserSettings(
                user_id=user_id,
                gender=gender,
                age=age,
                height=height,
                weight=weight,
                goal=goal,
                calorie_goal=targets["calories"],
                protein_goal=targets["protein"],
                fat_goal=targets["fat"],
                carb_goal=targets["carbs"],
                fiber_goal=targets.get("fiber", 30),
                water_goal=water_goal,
                is_initialized=True,
            )
            session.add(settings)

        # --- NEW: TRIAL LOGIC ---
        from datetime import datetime, timedelta

        from database.models import PAYMENT_SOURCE_TRIAL, Subscription

        # Check if they already have one
        stmt_sub = select(Subscription).where(Subscription.user_id == user_id)
        sub = (await session.execute(stmt_sub)).scalar_one_or_none()

        if not sub:
            # Grant 3 days of PRO by default for new users
            sub = Subscription(
                user_id=user_id,
                tier="pro",
                expires_at=datetime.now() + timedelta(days=3),
                is_active=True,
                payment_source=PAYMENT_SOURCE_TRIAL,
            )
            session.add(sub)
            # Also unlock AI Guide for the trial period
            settings.guide_active_until = datetime.now() + timedelta(days=3)

        # CRITICAL FIX: Mark user as verified so they never see password prompt again
        user_db = await session.get(User, user_id)
        if user_db:
            user_db.is_verified = True

        await session.commit()

    await state.clear()

    goal_text = {
        "lose_weight": "похудеть",
        "maintain": "не набирать",
        "healthy": "здоровое питание",
        "gain_mass": "набрать массу",
    }.get(goal, "здоровое питание")

    try:
        await message.delete()
    except Exception:
        pass

    first_name = message.chat.first_name or "друг"
    finish_text = (
        f"🎉 <b>Готово, {first_name}!</b>\n\n"
        "PRO активирован на 3 дня — всё открыто.\n\n"
        "━━━━━━━━━━━━━━━\n"
        "<b>Давай сразу попробуем.</b>\n"
        "Напиши, скажи голосом или сфоткай — что ты ел сегодня?\n\n"
        "<i>Например:</i>\n"
        "• <code>овсянка 200г на молоке</code>\n"
        "• <code>2 яйца, кофе с сахаром и бутер с сыром</code>\n"
        "• <code>борщ 300 грамм</code>\n\n"
        "Я посчитаю КБЖУ за 3 секунды ⚡\n\n"
        "<i>Если ещё не ел — просто напиши «ещё не ел».</i>"
    )

    await message.answer(finish_text, parse_mode="HTML")

    # Capture user while hot — ask if they've eaten today
    ate_builder = InlineKeyboardBuilder()
    ate_builder.button(text="🍳 Да, запишем!", callback_data="onboard_ate_yes")
    ate_builder.button(text="⏰ Нет, напомни в 8:00", callback_data="onboard_ate_no")
    ate_builder.adjust(1)
    await message.answer(
        "Кстати — ты сегодня уже ел что-нибудь? 🍽️",
        reply_markup=ate_builder.as_markup(),
    )


@router.callback_query(F.data == "onboard_ate_yes")
async def handle_onboard_ate_yes(callback: types.CallbackQuery) -> None:
    await callback.answer()
    try:
        await callback.message.edit_text(
            "Отлично! 💪 Просто напиши что ел — я всё посчитаю.\n\n"
            "<i>Например: «овсянка 200г, кофе с молоком»</i>",
            parse_mode="HTML",
        )
    except Exception:
        await callback.message.answer(
            "Отлично! 💪 Просто напиши что ел — я всё посчитаю.\n\n"
            "<i>Например: «овсянка 200г, кофе с молоком»</i>",
            parse_mode="HTML",
        )


@router.callback_query(F.data == "onboard_ate_no")
async def handle_onboard_ate_no(callback: types.CallbackQuery) -> None:
    user_id = callback.from_user.id
    async for session in get_db():
        existing = (await session.execute(
            select(UserFeedback).where(
                (UserFeedback.user_id == user_id) &
                (UserFeedback.feedback_type == "morning_reminder_v1")
            )
        )).scalar_one_or_none()
        if not existing:
            session.add(UserFeedback(
                user_id=user_id,
                feedback_type="morning_reminder_v1",
                answer="pending",
            ))
            await session.commit()
        break

    await callback.answer()
    try:
        await callback.message.edit_text(
            "Окей, напомню в 8:00 утра! ⏰\n\n"
            "Как проснёшься — запишем первый приём. Это займёт 10 секунд.",
        )
    except Exception:
        await callback.message.answer(
            "Окей, напомню в 8:00 утра! ⏰\n\n"
            "Как проснёшься — запишем первый приём. Это займёт 10 секунд.",
        )


@router.callback_query(F.data.startswith("onboarding_back:"))
async def handle_back(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Handle back button during onboarding.

    Args:
        callback: Telegram callback query
        state: FSM context

    Returns:
        None

    """
    step = callback.data.split(":")[1]

    if step == "gender":
        # Back from physical params or gender selection itself
        await state.set_state(OnboardingStates.waiting_for_gender)
        builder = InlineKeyboardBuilder()
        builder.button(text="👨 Мужской", callback_data="onboarding_gender:male")
        builder.button(text="👩 Женский", callback_data="onboarding_gender:female")
        builder.adjust(2)

        text = "1️⃣ Выбери свой пол:"
        try:
            await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        except Exception:
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")

    elif step == "goals":
        # Back to age from goal selection
        await state.set_state(OnboardingStates.waiting_for_age)
        
        text = (
            "<b>2️⃣ Напиши свой возраст:</b>\n\n"
            "Пример: <code>30</code>"
        )
        try:
            await callback.message.edit_text(text, parse_mode="HTML")
        except Exception:
            await callback.message.delete()
            await callback.message.answer(text, parse_mode="HTML")

    elif step == "to_goal_selection":
        # Back from calorie confirmation to goal selection
        await state.set_state(OnboardingStates.waiting_for_goal)
        data = await state.get_data()
        
        builder = InlineKeyboardBuilder()
        builder.button(text="📉 Похудеть", callback_data="onboarding_goal:lose_weight")
        builder.button(text="⚖️ Не набирать", callback_data="onboarding_goal:maintain")
        builder.button(text="🥗 Здоровое питание", callback_data="onboarding_goal:healthy")
        builder.button(text="💪 Набрать массу", callback_data="onboarding_goal:gain_mass")
        builder.adjust(2)

        text = (
            f"<b>✅ Данные приняты: {data.get('age')} лет, {data.get('height')} см, {data.get('weight')} кг</b>\n\n"
            "5️⃣ Выбери свою <b>главную цель</b>:"
        )
        try:
            await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        except Exception:
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")

    elif step == "calorie_confirmation":
        # Back to goals from manual input
        data = await state.get_data()
        goal = data.get("goal", "healthy")
        
        # We need to trigger handle_goal_selection again, but let's just show the goals with buttons
        await state.set_state(OnboardingStates.waiting_for_calorie_confirmation)
        
        # Recalculate if targets are lost, but they should be in state
        targets = data.get("pending_targets")
        if not targets:
            await callback.answer("Ошибка, выберите цель заново")
            return

        builder = InlineKeyboardBuilder()
        builder.button(text="✅ Принять (авто)", callback_data="onboarding_goals:accept")
        builder.button(text="✏️ Ввести свои калории", callback_data="onboarding_goals:manual")
        builder.adjust(1)

        text = (
            "🎯 <b>Проверь расчеты еще раз:</b>\n\n"
            f"🔥 <b>Калории: <code>{targets['calories']} ккал</code></b>\n"
            f"🥩 Белки: <code>{targets['protein']} г</code>\n"
            f"🥑 Жиры: <code>{targets['fat']} г</code>\n"
            f"🍞 Углеводы: <code>{targets['carbs']} г</code>\n\n"
            "<b>Согласен?</b>"
        )
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")

    await callback.answer()


@router.callback_query(F.data == "onboarding_start_fridge")
async def start_fridge_initialization(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Handle start fridge initialization button.

    Args:
        callback: Telegram callback query
        state: FSM context
    """
    await state.set_state(OnboardingStates.initializing_fridge)

    text = (
        "📸 <b>Заполнение холодильника</b>\n\n"
        "Сфотографируй продукты (этикетки или сами товары), которые у тебя есть.\n"
        "Я распознаю их и добавлю в твой виртуальный холодильник.\n\n"
        "Отправляй фото по одному или группой."
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="⏭️ Завершить (В Главное меню)", callback_data="onboarding_skip_fridge")
    builder.adjust(1)

    # Check if we can edit or need to send new message
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())

    await callback.answer()


@router.message(OnboardingStates.initializing_fridge, F.photo)
async def process_fridge_product_photo(message: types.Message, bot: Bot, state: FSMContext) -> None:
    """Handle product photo by adding it to the processing queue.

    This ensures sequential processing and prevents database locking issues.
    """
    photo = message.photo[-1]
    user_id = message.from_user.id

    # Notify user that we received the photo
    # (Optional, but good UX if processing is slow)
    # await message.answer("📸 Фото принято в обработку...")

    await PhotoQueueManager.add_item(
        user_id=user_id,
        message=message,
        bot=bot,
        state=state,
        processing_func=process_single_photo,
        file_id=photo.file_id
    )


async def process_single_photo(message: types.Message, bot: Bot, state: FSMContext, file_id: str) -> None:
    """Actual verification logic (extracted from handler).

    Args:
        message: Original message
        bot: Bot instance
        state: FSM context
        file_id: File ID to download
    """
    status_msg = await message.answer("⏳ Анализирую продукт...")

    try:
        file_info = await bot.get_file(file_id)
        photo_bytes = io.BytesIO()
        await bot.download_file(file_info.file_path, photo_bytes)

        # Try to recognize product (label or photo) using Shared AI Service
        from services.ai import AIService
        product_data = await AIService.recognize_product_from_image(photo_bytes.getvalue())

        if not product_data or not product_data.get("name"):
            raise ValueError("Не удалось распознать продукт. Попробуй сфотографировать этикетку или продукт более четко.")

        user_id = message.from_user.id

        # Create product directly for fridge init (no receipt)
        async for session in get_db():
            product = Product(
                user_id=user_id,
                source="fridge_init",
                name=product_data.get("name", "Неизвестный товар"),
                price=0.0,
                quantity=1.0,
                category=None,
                calories=float(product_data.get("calories", 0) or 0),
                protein=float(product_data.get("protein", 0) or 0),
                fat=float(product_data.get("fat", 0) or 0),
                carbs=float(product_data.get("carbs", 0) or 0),
            )
            session.add(product)
            await session.commit()
            await session.refresh(product)

            # Build snapshot of fridge (totals + last items) for contextual recs
            totals_stmt = select(
                func.sum(Product.calories),
                func.sum(Product.protein),
                func.sum(Product.fat),
                func.sum(Product.carbs),
            ).where(Product.user_id == user_id)
            totals_row = await session.execute(totals_stmt)
            totals = totals_row.fetchone() or (0, 0, 0, 0)

            names_stmt = (
                select(Product.name)
                .where(Product.user_id == user_id)
                .order_by(Product.id.desc())
                .limit(5)
            )
            name_rows = (await session.execute(names_stmt)).scalars().all()

            fridge_snapshot = {
                "totals": {
                    "calories": totals[0] or 0,
                    "protein": totals[1] or 0,
                    "fat": totals[2] or 0,
                    "carbs": totals[3] or 0,
                },
                "items": name_rows,
            }

            # Get consultant recommendations with fridge context
            settings_stmt = select(UserSettings).where(UserSettings.user_id == user_id)
            settings_result = await session.execute(settings_stmt)
            settings = settings_result.scalar_one_or_none()

            recommendation_text = ""
            if settings and settings.is_initialized:
                recommendations = await ConsultantService.analyze_product(
                    product, settings, context="fridge", fridge_snapshot=fridge_snapshot
                )
                warnings = recommendations.get("warnings", [])
                recs = recommendations.get("recommendations", [])
                missing = recommendations.get("missing", [])

                if warnings or recs or missing:
                    recommendation_text = "\n\n💡 <b>Рекомендации:</b>\n<blockquote>"
                    if warnings:
                        recommendation_text += "\n".join(warnings) + "\n"
                    if recs:
                        recommendation_text += "\n".join(recs) + "\n"
                    if missing:
                        recommendation_text += "\n".join(missing)
                    recommendation_text += "</blockquote>"

            break

        # Determine if it was a label or product photo
        source_type = "этикетка" if product_data.get("brand") or product_data.get("weight") else "фото продукта"
        kbzhu_note = "" if product_data.get("brand") else "\n<i>КБЖУ - усредненные значения</i>"

        builder = InlineKeyboardBuilder()
        builder.button(text="✅ Готово", callback_data="onboarding_finish_fridge")
        builder.button(text="⏭️ Пропустить", callback_data="onboarding_skip_fridge")
        builder.adjust(1)

        await status_msg.edit_text(
            f"✅ <b>Продукт добавлен в холодильник!</b> ({source_type})\n\n"
            f"📦 {product_data.get('name')}\n"
            + (f"🏷️ {product_data.get('brand')}\n" if product_data.get('brand') else "")
            + (f"⚖️ {product_data.get('weight')}\n" if product_data.get('weight') else "")
            + f"🔥 КБЖУ: {product_data.get('calories') or '—'}/"
            f"{product_data.get('protein') or '—'}/"
            f"{product_data.get('fat') or '—'}/"
            f"{product_data.get('carbs') or '—'}"
            + kbzhu_note
            + recommendation_text,
            parse_mode="HTML",
            reply_markup=builder.as_markup(),
        )

    except Exception as exc:
        builder = InlineKeyboardBuilder()
        builder.button(text="⏭️ В Главное меню", callback_data="onboarding_skip_fridge")
        builder.adjust(1)
        await status_msg.edit_text(
            f"❌ <b>Ошибка при распознавании:</b>\n<code>{exc}</code>\n\nПопробуйте ещё раз или перейдите в меню.",
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )


@router.callback_query(F.data == "onboarding_finish_fridge")
async def finish_fridge_initialization(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Finish fridge initialization and show main menu.

    Args:
        callback: Telegram callback query
        state: FSM context

    Returns:
        None

    """
    await state.clear()

    builder = InlineKeyboardBuilder()
    builder.button(text="🏠 Главное меню", callback_data="main_menu")
    builder.adjust(1)

    text = (
        "🎉 <b>Отлично! Холодильник инициализирован!</b>\n\n"
        "Теперь я знаю, какие продукты у тебя есть.\n"
        "Могу предлагать рецепты и следить за питанием!"
    )

    try:
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "onboarding_skip_fridge")
async def skip_fridge_initialization(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Skip fridge initialization and show main menu.

    Args:
        callback: Telegram callback query
        state: FSM context

    Returns:
        None

    """
    await state.clear()

    builder = InlineKeyboardBuilder()
    builder.button(text="🏠 Главное меню", callback_data="main_menu")
    builder.adjust(1)

    text = (
        "✅ <b>Настройка завершена!</b>\n\n"
        "Ты можешь заполнить холодильник позже, загрузив чек или отсканировав этикетки."
    )

    try:
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "force_onboarding")
async def force_onboarding(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Force restart onboarding from notification.

    Args:
        callback: Telegram callback query
        state: FSM context
    """
    # Clear any existing state
    await state.clear()

    # Start fresh onboarding
    await state.set_state(OnboardingStates.waiting_for_gender)

    builder = InlineKeyboardBuilder()
    builder.button(text="👨 Мужской", callback_data="onboarding_gender:male")
    builder.button(text="👩 Женский", callback_data="onboarding_gender:female")
    builder.adjust(2)

    welcome_text = (
        "🔄 <b>Обновление профиля</b>\n\n"
        "Давай обновим твои данные для более точных расчетов.\n\n"
        "1️⃣ Выбери свой пол:"
    )

    try:
        await callback.message.edit_text(welcome_text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        await callback.message.delete()
        await callback.message.answer(welcome_text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()
