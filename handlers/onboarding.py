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
from sqlalchemy import select

from database.base import get_db
from database.models import Product, Receipt, UserSettings
from handlers.menu import show_main_menu
import logging

from services.consultant import ConsultantService
from services.label_ocr import LabelOCRService

logger = logging.getLogger(__name__)

router = Router()


class OnboardingStates(StatesGroup):
    """FSM states for onboarding flow."""

    waiting_for_gender = State()
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
            await show_main_menu(message, message.from_user.first_name)
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
    await state.set_state(OnboardingStates.waiting_for_height)

    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="onboarding_back:gender")

    text = (
        "✅ Пол сохранен!\n\n"
        "2️⃣ Введите свой рост в сантиметрах (например: 175):"
    )

    try:
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


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
            "3️⃣ Введите свой вес в килограммах (например: 70.5):"
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
            "4️⃣ Выбери свою цель:"
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

        if settings:
            settings.gender = data.get("gender")
            settings.height = data.get("height")
            settings.weight = data.get("weight")
            settings.goal = goal
            settings.is_initialized = True
            await session.commit()
        else:
            settings = UserSettings(
                user_id=user_id,
                gender=data.get("gender"),
                height=data.get("height"),
                weight=data.get("weight"),
                goal=goal,
                is_initialized=True,
            )
            session.add(settings)
            await session.commit()

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


async def _recognize_product_from_photo(image_bytes: bytes) -> dict[str, Any] | None:
    """Recognize product from photo and get average KBZHU.

    First tries to parse as label, if fails - recognizes as product photo
    and gets average nutrition values.

    Args:
        image_bytes: Raw image bytes

    Returns:
        Dictionary with product info: name, brand, weight, calories, protein, fat, carbs
        Or None if recognition fails

    """
    import base64
    import json
    import re

    import aiohttp

    from config import settings

    # First try: parse as label (has KBZHU on it)
    label_data = await LabelOCRService.parse_label(image_bytes)
    if label_data and label_data.get("name") and label_data.get("calories"):
        return label_data

    # Second try: recognize product and get average KBZHU
    base64_image = base64.b64encode(image_bytes).decode("utf-8")

    prompt = (
        "Ты видишь фото продукта питания. Определи что это за продукт и верни усредненные значения КБЖУ.\n\n"
        "Верни ТОЛЬКО JSON объект (без markdown) в формате:\n"
        '{"name": "Название продукта на русском", '
        '"brand": null, '
        '"weight": null, '
        '"calories": 0, '
        '"protein": 0.0, '
        '"fat": 0.0, '
        '"carbs": 0.0}\n\n'
        "calories, protein, fat, carbs - это усредненные значения на 100г для этого типа продукта.\n"
        "Например, для яблока: calories=52, protein=0.3, fat=0.2, carbs=14.\n"
        "Для молока 3.2%: calories=64, protein=3.0, fat=3.2, carbs=4.7.\n"
        "Если не можешь определить - верни null для всех полей."
    )

    models = [
        "qwen/qwen2.5-vl-32b-instruct:free",
        "google/gemini-2.0-flash-exp:free",
        "google/gemini-2.5-flash-lite-preview-09-2025",
        "openai/gpt-4.1-mini",
    ]

    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://foodflow.app",
        "X-Title": "FoodFlow Bot",
    }

    import asyncio

    for model in models:
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                        },
                    ],
                }
            ],
        }

        for attempt in range(3):
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers=headers,
                        json=payload,
                        timeout=20,
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            content = result["choices"][0]["message"]["content"]
                            # Clean markdown
                            content = content.replace("```json", "").replace("```", "").strip()
                            # Extract JSON
                            json_match = re.search(r"\{.*\}", content, re.DOTALL)
                            if json_match:
                                content = json_match.group(0)
                            data = json.loads(content)
                            if data.get("name"):
                                return data
                        else:
                            if attempt < 2:
                                await asyncio.sleep(0.5)
                                continue
                except Exception as e:
                    logger.error(f"Error recognizing product ({model}) attempt {attempt+1}/3: {e}")
                    if attempt < 2:
                        await asyncio.sleep(0.5)
                        continue

    return None


@router.callback_query(F.data == "onboarding_start_fridge")
async def start_fridge_initialization(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Start fridge initialization by scanning product labels.

    Args:
        callback: Telegram callback query
        state: FSM context

    Returns:
        None

    """
    await state.set_state(OnboardingStates.initializing_fridge)

    text = (
        "📦 <b>Инициализация холодильника</b>\n\n"
        "Отсканируй этикетки продуктов или просто сфотографируй продукты, которые есть у тебя дома.\n"
        "Я распознаю название и добавлю усредненные КБЖУ.\n\n"
        "Можешь отсканировать несколько продуктов подряд.\n"
        "Когда закончишь - нажми «✅ Готово»."
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Готово", callback_data="onboarding_finish_fridge")
    builder.button(text="⏭️ Пропустить", callback_data="onboarding_skip_fridge")
    builder.adjust(1)

    try:
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.message(OnboardingStates.initializing_fridge, F.photo)
async def process_fridge_product_photo(message: types.Message, bot: Bot, state: FSMContext) -> None:
    """Process product photo during fridge initialization.

    Tries to recognize as label first, then as product photo with average KBZHU.

    Args:
        message: Telegram message with product photo
        bot: Telegram bot instance
        state: FSM context

    Returns:
        None

    """
    status_msg = await message.answer("⏳ Анализирую продукт...")

    try:
        photo = message.photo[-1]
        file_info = await bot.get_file(photo.file_id)
        photo_bytes = io.BytesIO()
        await bot.download_file(file_info.file_path, photo_bytes)

        # Try to recognize product (label or photo)
        product_data = await _recognize_product_from_photo(photo_bytes.getvalue())
        if not product_data or not product_data.get("name"):
            raise ValueError("Не удалось распознать продукт. Попробуй сфотографировать этикетку или продукт более четко.")

        user_id = message.from_user.id

        # Create a receipt for onboarding products
        async for session in get_db():
            receipt = Receipt(
                user_id=user_id,
                raw_text="onboarding_initialization",
                total_amount=0.0
            )
            session.add(receipt)
            await session.flush()

            # Create product from recognized data
            product = Product(
                receipt_id=receipt.id,
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

            # Get consultant recommendations
            settings_stmt = select(UserSettings).where(UserSettings.user_id == user_id)
            settings_result = await session.execute(settings_stmt)
            settings = settings_result.scalar_one_or_none()

            recommendation_text = ""
            if settings and settings.is_initialized:
                recommendations = await ConsultantService.analyze_product(
                    product, settings, context="fridge"
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
            parse_mode="HTML"
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

