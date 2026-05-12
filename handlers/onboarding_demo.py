"""Interactive demo flow shown right after onboarding.

The bot "demonstrates" how food logging works by:
1. Sending a photo of a meal
2. Simulating AI analysis with live-updating status messages
3. Showing the KBJU result
4. "Confirming" the entry
5. Cleaning up all demo messages
6. Presenting quick-start buttons for the user's first real log

This eliminates the blank-page problem and gives instant "wow".
"""
import asyncio
import logging

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router()
logger = logging.getLogger(__name__)

# Hardcoded demo data (scrambled eggs + bread + coffee)
DEMO_FOOD = {
    "name": "Яичница с помидорами, хлеб с маслом, кофе с молоком",
    "calories": 420,
    "protein": 18.5,
    "fat": 22.3,
    "carbs": 38.7,
    "fiber": 2.1,
}


async def run_onboarding_demo(message: types.Message, state: FSMContext) -> None:
    """Run the interactive demo right after onboarding finishes.

    Sends a series of messages simulating the food logging flow,
    then cleans up and shows quick-start buttons.
    """
    messages_to_delete_ids = []

    try:
        # ── Step 1: Intro ──────────────────────────────────────
        intro_msg = await message.answer(
            "🎬 <b>Сейчас покажу, как это работает — смотри!</b>",
            parse_mode="HTML",
            reply_markup=types.ReplyKeyboardRemove()
        )
        messages_to_delete_ids.append(intro_msg.message_id)
        await asyncio.sleep(1.5)

        # ── Step 2: Send demo food photo ───────────────────────
        photo = types.FSInputFile("assets/demo_breakfast.png")
        photo_msg = await message.answer_photo(
            photo=photo,
            caption="📸 <i>Представь, что это твой завтрак. Вот как я разберу такое фото 👇</i>",
            parse_mode="HTML",
        )
        messages_to_delete_ids.append(photo_msg.message_id)
        await asyncio.sleep(2.0)

        # ── Step 3: Simulate AI analysis ───────────────────────
        status_msg = await message.answer(
            "👀 <b>Смотрю, что на фото...</b>",
            parse_mode="HTML",
        )
        messages_to_delete_ids.append(status_msg.message_id)
        await asyncio.sleep(1.5)

        await status_msg.edit_text(
            "🧠 <b>Анализирую...</b> <i>яичница, хлеб, кофе</i>",
            parse_mode="HTML",
        )
        await asyncio.sleep(1.5)

        await status_msg.edit_text(
            "🔢 <b>Считаю КБЖУ...</b>",
            parse_mode="HTML",
        )
        await asyncio.sleep(1.0)

        # ── Step 4: Show result card ───────────────────────────
        result_text = (
            "✅ <b>Готово!</b>\n\n"
            f"🍽️ <b>{DEMO_FOOD['name']}</b>\n\n"
            f"🔥 Калории: <code>{DEMO_FOOD['calories']}</code> ккал\n"
            f"🥩 Белки: <code>{DEMO_FOOD['protein']}</code> | "
            f"🥑 Жиры: <code>{DEMO_FOOD['fat']}</code> | "
            f"🍞 Углеводы: <code>{DEMO_FOOD['carbs']}</code>\n"
            f"🥬 Клетчатка: <code>{DEMO_FOOD['fiber']}</code>\n\n"
            "⏱ <b>3 секунды — и всё посчитано!</b>"
        )

        await status_msg.edit_text(result_text, parse_mode="HTML")
        
        # ── Step 5: Transition to Onboarding ───────────────────
        builder = InlineKeyboardBuilder()
        builder.button(text="🚀 НАСТРОИТЬ МОЙ ПРОФИЛЬ 🚀", callback_data="demo_start_onboarding")
        builder.adjust(1)

        final_text = (
            "✨ <b>Вот так просто!</b>\n\n"
            "Фото, голос или текст — я пойму всё.\n"
            "Не нужно знать граммы — я подскажу.\n\n"
            "━━━━━━━━━━━━━━━\n\n"
            "Чтобы считать калории под твой вес и цель (похудение/поддержание/набор), давай быстро настроим профиль! 👇"
        )

        bridge_msg = await message.answer(final_text, parse_mode="HTML", reply_markup=builder.as_markup())
        messages_to_delete_ids.append(bridge_msg.message_id)
        
        # Save message IDs for later cleanup
        await state.update_data(demo_message_ids=messages_to_delete_ids)

    except Exception as e:
        logger.error(f"Onboarding demo error: {e}", exc_info=True)
        # Fallback: just show start onboarding button
        builder = InlineKeyboardBuilder()
        builder.button(text="🚀 Настроить профиль", callback_data="demo_start_onboarding")
        builder.adjust(1)

        await message.answer(
            "🎉 <b>Всё готово!</b>\n\n"
            "Давай настроим твой профиль, чтобы начать считать КБЖУ!",
            parse_mode="HTML",
            reply_markup=builder.as_markup(),
        )


@router.callback_query(F.data == "demo_start_onboarding")
async def handle_demo_start_onboarding(callback: types.CallbackQuery, state: FSMContext) -> None:
    """User finished demo and wants to setup profile."""
    from handlers.onboarding import start_onboarding
    await callback.answer()
    
    # Clean up demo messages
    data = await state.get_data()
    msg_ids = data.get("demo_message_ids", [])
    for m_id in msg_ids:
        try:
            await callback.bot.delete_message(chat_id=callback.message.chat.id, message_id=m_id)
        except Exception:
            pass
    
    try:
        await callback.message.delete()
    except Exception:
        pass
    await start_onboarding(callback.message, state)


@router.callback_query(F.data.startswith("demo_quick:"))
async def handle_demo_quick(callback: types.CallbackQuery) -> None:
    """User tapped a quick-food button from the demo finish screen."""
    food_text = callback.data.split(":", 1)[1]
    await callback.answer()

    # Delete the quick-start message
    try:
        await callback.message.delete()
    except Exception:
        pass

    # Route to the real food logging flow via universal_input

    # We need FSM state — get it from the middleware data
    # Since we can't easily get state here, simulate a text message approach:
    # Just send a synthetic processing call
    status_msg = await callback.message.answer(
        f"🧠 <b>Анализирую:</b> <blockquote>{food_text}</blockquote>",
        parse_mode="HTML",
    )

    try:
        from services.normalization import NormalizationService
        from utils.parsing import safe_float

        result = await NormalizationService.analyze_food_intake(food_text)

        name = result.get("name", food_text)
        calories = safe_float(result.get("calories"))
        protein = safe_float(result.get("protein"))
        fat = safe_float(result.get("fat"))
        carbs = safe_float(result.get("carbs"))
        fiber = safe_float(result.get("fiber"))
        weight_grams = result.get("weight_grams")

        display_name = f"{name} ({weight_grams}г)" if weight_grams else name

        # Save directly to DB (skip confirmation for first quick-log to reduce friction)
        from datetime import datetime

        from database.base import get_db
        from database.models import ConsumptionLog

        async for session in get_db():
            log = ConsumptionLog(
                user_id=callback.from_user.id,
                product_name=display_name,
                base_name=name,
                calories=calories,
                protein=protein,
                fat=fat,
                carbs=carbs,
                fiber=fiber,
                date=datetime.now(),
            )
            session.add(log)
            await session.commit()
            
            # Log event for analytics (triggers food_logged_first_time, etc.)
            from utils.analytics import log_event
            await log_event(callback.from_user.id, "food_logged")
            break

        fiber_line = f"\n🥬 Клетчатка: <code>{fiber:.1f}</code>" if fiber else ""
        success_text = (
            f"✅ <b>Записано!</b> 🎉\n\n"
            f"🍽️ <b>{display_name}</b>\n\n"
            f"🔥 <code>{int(calories)}</code> ккал\n"
            f"🥩 <code>{protein:.1f}</code> | 🥑 <code>{fat:.1f}</code> | 🍞 <code>{carbs:.1f}</code>"
            f"{fiber_line}\n\n"
            f"🏆 <b>Первая запись в дневнике!</b>\n\n"
            f"<b>Теперь попробуй сам!</b> Отправь фото, голос или текст своей еды прямо сейчас 👇"
        )

        builder = InlineKeyboardBuilder()
        builder.button(text="🚀 ВВЕСТИ СВОЮ ЕДУ (фото/голос) 🚀", callback_data="menu_i_ate")
        builder.button(text="🏠 В меню", callback_data="main_menu")
        builder.adjust(1)

        await status_msg.edit_text(success_text, parse_mode="HTML", reply_markup=builder.as_markup())

    except Exception as e:
        logger.error(f"Demo quick log error: {e}", exc_info=True)
        await status_msg.edit_text(
            f"❌ Ошибка: {e}\n\nПопробуйте записать через меню.",
        )


@router.callback_query(F.data == "demo_not_yet")
async def handle_demo_not_yet(callback: types.CallbackQuery) -> None:
    """User hasn't eaten yet — show menu instead of silence."""
    await callback.answer()

    try:
        await callback.message.delete()
    except Exception:
        pass

    # Save morning reminder preference
    from sqlalchemy import and_, select

    from database.base import get_db
    from database.models import UserFeedback

    async for session in get_db():
        existing = (await session.execute(
            select(UserFeedback).where(
                and_(
                    UserFeedback.user_id == callback.from_user.id,
                    UserFeedback.feedback_type == "morning_reminder_v1",
                )
            )
        )).scalar_one_or_none()
        if not existing:
            session.add(UserFeedback(
                user_id=callback.from_user.id,
                feedback_type="morning_reminder_v1",
                answer="pending",
            ))
            await session.commit()
        break

    await callback.message.answer(
        "⏰ <b>Напомню позже!</b>\n\n"
        "А пока — посмотри, что я умею 👇",
        parse_mode="HTML",
    )

    # Show main menu so user sees the full dashboard
    from handlers.menu import show_main_menu
    await show_main_menu(
        callback.message,
        callback.from_user.first_name,
        callback.from_user.id,
    )
