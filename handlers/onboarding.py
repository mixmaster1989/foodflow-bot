"""Module for user onboarding (initial setup).

Contains:
- OnboardingStates: FSM states for onboarding flow
- start_onboarding: Start onboarding process
- handle_gender_selection: Handle gender selection
- handle_height_input: Handle height input
- handle_weight_input: Handle weight input
- handle_goal_selection: Handle goal selection
- finish_onboarding: Save data and complete onboarding
"""
import io
from typing import Any

from aiogram import Bot, F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, func

from database.base import get_db
from database.models import Product, Receipt, UserSettings
from handlers.menu import show_main_menu
import logging

from services.consultant import ConsultantService
from services.photo_queue import PhotoQueueManager
from services.label_ocr import LabelOCRService

logger = logging.getLogger(__name__)

router = Router()


class OnboardingStates(StatesGroup):
    """FSM states for onboarding flow."""

    waiting_for_gender = State()
    waiting_for_age = State()  # NEW: Age input
    waiting_for_height = State()
    waiting_for_weight = State()
    waiting_for_goal = State()
    initializing_fridge = State()  # Scanning products for initial fridge setup


async def start_onboarding(message: types.Message, state: FSMContext) -> None:
    """Start onboarding process for new users.

    Checks if user has completed onboarding, if not - starts the flow.

    Args:
        message: Telegram message
        state: FSM context

    Returns:
        None

    """
    user_id: int = message.from_user.id

    async for session in get_db():
        stmt = select(UserSettings).where(UserSettings.user_id == user_id)
        settings = (await session.execute(stmt)).scalar_one_or_none()

        # If user already initialized, show main menu
        if settings and settings.is_initialized:
            await show_main_menu(message, message.from_user.first_name, message.from_user.id)
            return

        # Start onboarding
        await state.set_state(OnboardingStates.waiting_for_gender)

        builder = InlineKeyboardBuilder()
        builder.button(text="👨 Мужской", callback_data="onboarding_gender:male")
        builder.button(text="👩 Женский", callback_data="onboarding_gender:female")
        builder.adjust(2)

        welcome_text = (
            "👋 <b>Добро пожаловать в FoodFlow!</b>\n\n"
            "Я помогу тебе следить за питанием и управлять продуктами.\n\n"
            "Для начала мне нужно узнать немного о тебе:\n\n"
            "1️⃣ Выбери свой пол:"
        )

        await message.answer(welcome_text, reply_markup=builder.as_markup(), parse_mode="HTML")


@router.callback_query(F.data.startswith("onboarding_gender:"))
async def handle_gender_selection(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Handle gender selection.

    Args:
        callback: Telegram callback query with gender data
        state: FSM context

    Returns:
        None

    """
    gender = callback.data.split(":")[1]  # "male" or "female"
    await state.update_data(gender=gender)
    await state.set_state(OnboardingStates.waiting_for_age)

    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="onboarding_back:gender")

    text = (
        "✅ Пол сохранен!\n\n"
        "2️⃣ Введите свой возраст (полных лет):"
    )

    try:
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.message(OnboardingStates.waiting_for_age)
async def handle_age_input(message: types.Message, state: FSMContext) -> None:
    """Handle age input.

    Args:
        message: Telegram message with age
        state: FSM context
    """
    try:
        age: int = int(message.text) if message.text else 0
        if age < 14 or age > 100:
            await message.answer("Пожалуйста, введите корректный возраст (14-100 лет):")
            return

        await state.update_data(age=age)
        await state.set_state(OnboardingStates.waiting_for_height)

        builder = InlineKeyboardBuilder()
        builder.button(text="🔙 Назад", callback_data="onboarding_back:age")

        text = (
            "✅ Возраст сохранен!\n\n"
            "3️⃣ Введите свой рост в сантиметрах (например: 175):"
        )

        await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except ValueError:
        await message.answer("Пожалуйста, введите целое число (возраст в годах):")


@router.message(OnboardingStates.waiting_for_height)
async def handle_height_input(message: types.Message, state: FSMContext) -> None:
    """Handle height input.

    Args:
        message: Telegram message with height
        state: FSM context

    Returns:
        None

    """
    try:
        height: int = int(message.text) if message.text else 0
        if height < 50 or height > 250:
            await message.answer("Пожалуйста, введите корректный рост (50-250 см):")
            return

        await state.update_data(height=height)
        await state.set_state(OnboardingStates.waiting_for_weight)

        builder = InlineKeyboardBuilder()
        builder.button(text="🔙 Назад", callback_data="onboarding_back:height")

        text = (
            "✅ Рост сохранен!\n\n"
            "4️⃣ Введите свой вес в килограммах (например: 70.5):"
        )

        await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except ValueError:
        await message.answer("Пожалуйста, введите целое число (рост в см):")


@router.message(OnboardingStates.waiting_for_weight)
async def handle_weight_input(message: types.Message, state: FSMContext) -> None:
    """Handle weight input.

    Args:
        message: Telegram message with weight
        state: FSM context

    Returns:
        None

    """
    try:
        weight: float = float(message.text.replace(",", ".")) if message.text else 0.0
        if weight < 20 or weight > 300:
            await message.answer("Пожалуйста, введите корректный вес (20-300 кг):")
            return

        await state.update_data(weight=weight)
        await state.set_state(OnboardingStates.waiting_for_goal)

        builder = InlineKeyboardBuilder()
        builder.button(text="📉 Похудеть", callback_data="onboarding_goal:lose_weight")
        builder.button(text="⚖️ Не толстеть", callback_data="onboarding_goal:maintain")
        builder.button(text="🥗 Здоровое питание", callback_data="onboarding_goal:healthy")
        builder.button(text="💪 Набрать массу", callback_data="onboarding_goal:gain_mass")
        builder.adjust(2)

        text = (
            "✅ Вес сохранен!\n\n"
            "5️⃣ Выбери свою цель:"
        )

        await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except ValueError:
        await message.answer("Пожалуйста, введите число (вес в кг, можно с десятичной точкой):")


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
    data = await state.get_data()

    user_id: int = callback.from_user.id

    async for session in get_db():
        stmt = select(UserSettings).where(UserSettings.user_id == user_id)
        settings = (await session.execute(stmt)).scalar_one_or_none()

        # Calculate KBZHU using Mifflin-St Jeor formula
        gender = data.get("gender", "male")
        age = data.get("age", 30)
        height = data.get("height", 170)
        weight = data.get("weight", 70)
        
        # BMR calculation (Mifflin-St Jeor)
        if gender == "male":
            bmr = 10 * weight + 6.25 * height - 5 * age + 5
        else:
            bmr = 10 * weight + 6.25 * height - 5 * age - 161
        
        # Activity multiplier (assuming moderate activity)
        tdee = bmr * 1.55
        
        # Adjust for goal
        if goal == "lose_weight":
            calories = int(tdee * 0.8)  # 20% deficit
        elif goal == "gain_mass":
            calories = int(tdee * 1.15)  # 15% surplus
        else:
            calories = int(tdee)
        
        # Macros distribution
        protein = int(weight * 1.8)  # 1.8g per kg body weight
        fat = int(calories * 0.25 / 9)  # 25% of calories from fat
        carbs = int((calories - protein * 4 - fat * 9) / 4)  # Rest from carbs

        if settings:
            settings.gender = gender
            settings.age = age
            settings.height = height
            settings.weight = weight
            settings.goal = goal
            settings.calorie_goal = calories
            settings.protein_goal = protein
            settings.fat_goal = fat
            settings.carb_goal = carbs
            settings.is_initialized = True
            await session.commit()
        else:
            settings = UserSettings(
                user_id=user_id,
                gender=gender,
                age=age,
                height=height,
                weight=weight,
                goal=goal,
                calorie_goal=calories,
                protein_goal=protein,
                fat_goal=fat,
                carb_goal=carbs,
                is_initialized=True,
            )
            session.add(settings)

    await state.clear()

    goal_text = {
        "lose_weight": "похудеть",
        "maintain": "не толстеть",
        "healthy": "здоровое питание",
        "gain_mass": "набрать массу",
    }.get(goal, "здоровое питание")

    try:
        await callback.message.delete()
    except Exception:
        pass

    finish_text = (
        "🎉 <b>Отлично! Настройка завершена!</b>\n\n"
        f"📋 Твой профиль:\n"
        f"👤 Пол: {'Мужской' if data.get('gender') == 'male' else 'Женский'}\n"
        f"🎂 Возраст: {data.get('age')} лет\n"
        f"📏 Рост: {data.get('height')} см\n"
        f"⚖️ Вес: {data.get('weight')} кг\n"
        f"🎯 Цель: {goal_text}\n\n"
        "Теперь я буду давать тебе персональные рекомендации по продуктам!"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="📦 Заполнить холодильник", callback_data="onboarding_start_fridge")
    builder.button(text="⏭️ Пропустить", callback_data="onboarding_skip_fridge")
    builder.adjust(1)

    await callback.message.answer(finish_text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


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
    elif step == "height":
        await state.set_state(OnboardingStates.waiting_for_height)
        builder = InlineKeyboardBuilder()
        builder.button(text="🔙 Назад", callback_data="onboarding_back:gender")

        text = "2️⃣ Введите свой рост в сантиметрах (например: 175):"
        try:
            await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        except Exception:
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")

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
    
    # Check if we can edit or need to send new message
    try:
        await callback.message.edit_text(text, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, parse_mode="HTML")
        
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
                    recommendation_text = "\n\n💡 <b>Рекомендации:</b>\n"
                    if warnings:
                        recommendation_text += "\n".join(warnings) + "\n"
                    if recs:
                        recommendation_text += "\n".join(recs) + "\n"
                    if missing:
                        recommendation_text += "\n".join(missing)

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
        await status_msg.edit_text(f"❌ Ошибка при распознавании: {exc}")


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
