"""Handler for quick food logging via text description."""
import logging
from datetime import datetime

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from sqlalchemy import select, func

from config import settings
from database.base import get_db
from database.models import ConsumptionLog
from services.normalization import NormalizationService
from services.ai_guide import AIGuideService
from utils.parsing import safe_float

router = Router()
logger = logging.getLogger(__name__)


class IAteStates(StatesGroup):
    waiting_for_description = State()
    waiting_for_weight = State()
    waiting_for_confirmation = State()
    waiting_for_edit_value = State()
    waiting_for_time = State()


@router.callback_query(F.data == "menu_i_ate")
async def i_ate_start(callback: types.CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(IAteStates.waiting_for_description)

    photo_path = types.FSInputFile("assets/i_ate.png")

    builder = InlineKeyboardBuilder()
    builder.button(text="⭐ Мои блюда", callback_data="menu_saved_dishes")
    builder.button(text="🏗️ Собрать блюдо", callback_data="menu_build_dish")
    builder.button(text="❌ Отмена", callback_data="main_menu")
    builder.adjust(2, 1)

    caption = (
        "🍽️ <b>Что съел(а)?</b>\n\n"
        "Напиши, скажи голосом или сфоткай.\n\n"
        "<i>Примеры:</i>\n"
        "• <code>овсянка 200г на молоке</code>\n"
        "• <code>2 яйца и кофе с сахаром</code>\n"
        "• <code>борщ 300 грамм</code>\n\n"
        "Если продукт часто повторяется — сохрани его в «⭐ Мои блюда»."
    )

    try:
        await callback.message.edit_media(
            media=types.InputMediaPhoto(media=photo_path, caption=caption, parse_mode="HTML"),
            reply_markup=builder.as_markup()
        )
    except Exception:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer_photo(
            photo=photo_path,
            caption=caption,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )


@router.message(IAteStates.waiting_for_description)
async def i_ate_process(message: types.Message, state: FSMContext) -> None:
    """Process food description, get KBJU from AI, save to consumption log."""
    description = message.text or message.caption

    # Voice message support: transcribe via STT
    if not description and message.voice:
        status_msg = await message.answer("🎤 <i>Распознаю голос...</i>", parse_mode="HTML")
        try:
            import os

            from aiogram import Bot

            from services.voice_stt import SpeechToText

            bot = Bot(token=settings.BOT_TOKEN)
            stt = SpeechToText()

            file_info = await bot.get_file(message.voice.file_id)
            temp_dir = "services/temp"
            os.makedirs(temp_dir, exist_ok=True)
            ogg_path = f"{temp_dir}/i_ate_voice_{message.voice.file_id}.ogg"

            await bot.download_file(file_info.file_path, ogg_path)
            description = await stt.process_voice_message(ogg_path)

            try:
                os.remove(ogg_path)
            except Exception:
                pass
            await bot.session.close()

            if not description:
                await status_msg.edit_text("❌ Не удалось распознать голос. Попробуйте ещё раз или напишите текстом.")
                return

            await status_msg.edit_text(f"🎤 <b>Распознано:</b> <blockquote>{description}</blockquote>", parse_mode="HTML")
            logger.info(f"🎤 I_ATE STT: {description}")
        except Exception as e:
            logger.error(f"I_ATE STT Error: {e}")
            await message.answer(f"❌ Ошибка распознавания: {e}")
            return

    # Photo support: analyze via Vision if no text/caption
    if not description and message.photo:
        status_msg = await message.answer("👀 <b>Смотрю, что на фото...</b>", parse_mode="HTML")
        try:
            from services.ai_brain import AIBrainService
            description = await AIBrainService.analyze_image(message, prompt="Что на фото? Опиши еду кратко.")
            if not description:
                await status_msg.edit_text("❌ Не удалось понять, что на фото. Попробуйте написать текстом.")
                return
            
            await status_msg.edit_text(f"👀 <b>Вижу:</b> <blockquote>{description}</blockquote>", parse_mode="HTML")
            logger.info(f"📸 I_ATE Vision: {description}")
        except Exception as e:
            logger.error(f"I_ATE Vision Error: {e}")
            await status_msg.edit_text(f"❌ Ошибка анализа фото: {e}")
            return

    if not description:
        await message.answer("⚠️ Пожалуйста, напишите название блюда текстом (или отправьте фото/голосовое с описанием).")
        return

    description = description.strip()

    status_msg = await message.answer("🔄 <b>Анализирую информацию...</b>", parse_mode="HTML")

    try:
        # Check if multi-item input via AI Brain
        from services.ai_brain import AIBrainService
        brain_result = await AIBrainService.analyze_text(description)

        if brain_result and isinstance(brain_result, dict) and brain_result.get("multi") and brain_result.get("items"):
            items = brain_result["items"]
            if len(items) > 1:
                # Route to batch flow (from universal_input)
                from handlers.universal_input import process_batch_food_logging
                await process_batch_food_logging(message, state, items, status_msg)
                return

        # Also handle raw list from AI
        if brain_result and isinstance(brain_result, list) and len(brain_result) > 1:
            items = [{"product": item.get("product") or item.get("name", ""), "weight": item.get("weight")} for item in brain_result if isinstance(item, dict)]
            if items:
                from handlers.universal_input import process_batch_food_logging
                await process_batch_food_logging(message, state, items, status_msg)
                return

        # Single item: use NormalizationService as before
        result = await NormalizationService.analyze_food_intake(description)

        name = result.get("name", description)
        calories = safe_float(result.get("calories"))
        protein = safe_float(result.get("protein"))
        fat = safe_float(result.get("fat"))
        carbs = safe_float(result.get("carbs"))
        fiber = safe_float(result.get("fiber"))
        weight_grams = result.get("weight_grams")
        weight_missing = result.get("weight_missing", True)
        base_name = result.get("base_name")

        logger.info(
            "KBJU_FLOW i_ate_process analyzed user_id=%s desc=%r -> name=%r base=%r weight_grams=%r weight_missing=%r kbju={kcal:%s p:%s f:%s c:%s fi:%s}",
            message.from_user.id,
            description,
            name,
            base_name,
            weight_grams,
            weight_missing,
            calories,
            protein,
            fat,
            carbs,
            fiber,
        )

        # If weight is missing, ask user to specify
        if weight_missing:
            # Save context and ask for weight
            await state.update_data(
                pending_product={
                    "name": name,
                    "base_name": base_name,
                    "calories100": calories,
                    "protein100": protein,
                    "fat100": fat,
                    "carbs100": carbs,
                    "fiber100": fiber,
                    "original_text": description
                }
            )
            await state.set_state(IAteStates.waiting_for_weight)

            builder = InlineKeyboardBuilder()
            builder.button(text="❌ Отмена", callback_data="main_menu")

            await status_msg.edit_text(
                f"🧐 Вы сказали: <blockquote>{description}</blockquote>\n"
                f"Это похоже на: <b>{name}</b>\n\n"
                f"⚖️ <b>Сколько грамм?</b>\n(Введите число, например: <code>150</code>)",
                parse_mode="HTML",
                reply_markup=builder.as_markup()
            )
            return

        # Happy path: Weight was detected
        await state.update_data(
            pending_product={
                "name": f"{name} ({weight_grams}г)",
                "base_name": base_name,
                "calories100": calories,
                "protein100": protein,
                "fat100": fat,
                "carbs100": carbs,
                "fiber100": fiber,
                "original_text": description
            }
        )

        logger.info(
            "KBJU_FLOW i_ate_process pending_product_ready user_id=%s name=%r base=%r stored_keys=calories100..fiber100 totals?=%r",
            message.from_user.id,
            f"{name} ({weight_grams}г)",
            base_name,
            True,
        )

        # Instead of saving immediately, show confirmation
        await show_confirmation_interface(message, state, status_msg)

    except Exception as e:
        logger.error(f"Error in i_ate_process: {e}", exc_info=True)
        await state.clear()
        await status_msg.edit_text(f"❌ Ошибка: {e}\n\nПопробуйте ещё раз.")


@router.message(IAteStates.waiting_for_weight, F.text)
async def handle_weight_input(message: types.Message, state: FSMContext) -> None:
    """Handle weight input (e.g., '55') after manual entry."""
    try:
        weight_text = message.text.replace(',', '.').strip()
        # Extract number if mixed text (e.g. "55g")
        import re
        match = re.search(r'(\d+(?:\.\d+)?)', weight_text)

        if not match:
            await message.reply("⚠️ Пожалуйста, введите только число (вес в граммах).")
            return

        weight = float(match.group(1))

        data = await state.get_data()
        product = data.get("pending_product")

        if not product:
            await message.reply("⚠️ Ошибка контекста. Попробуйте ввести продукт заново.")
            await state.clear()
            return

        # Recalculate based on weight
        factor = weight / 100.0

        name = product['name']
        base_name = product['base_name']
        prev = {
            "calories100": product.get("calories100"),
            "protein100": product.get("protein100"),
            "fat100": product.get("fat100"),
            "carbs100": product.get("carbs100"),
            "fiber100": product.get("fiber100"),
        }
        expected = {
            "calories": safe_float(product.get("calories100")) * factor,
            "protein": safe_float(product.get("protein100")) * factor,
            "fat": safe_float(product.get("fat100")) * factor,
            "carbs": safe_float(product.get("carbs100")) * factor,
            "fiber": safe_float(product.get("fiber100")) * factor,
        }
        logger.info(
            "KBJU_FLOW i_ate_weight_input user_id=%s raw_weight=%r parsed_weight=%s factor=%s prev=%s expected_totals=%s",
            message.from_user.id,
            message.text,
            weight,
            factor,
            prev,
            expected,
        )

        f"{name} ({int(weight)}г)"

        # Update pending product with new weight + apply recalculation.
        # If the AI returned values per 100g (weight_missing=True), this converts them to totals for the chosen weight.
        product["calories100"] = expected["calories"]
        product["protein100"] = expected["protein"]
        product["fat100"] = expected["fat"]
        product["carbs100"] = expected["carbs"]
        product["fiber100"] = expected["fiber"]

        # FIX: Prevent double weight ("Apple (100g) (200g)")
        # Use base_name if available, otherwise try to strip existing weight
        if base_name:
             product['name'] = f"{base_name} ({int(weight)}г)"
        else:
             # Fallback: remove existing (...) from name
             clean_name = re.sub(r'\s*\(\d+г\)$', '', name)
             product['name'] = f"{clean_name} ({int(weight)}г)"

        # Updating state
        await state.update_data(pending_product=product)

        logger.info(
            "KBJU_FLOW i_ate_weight_input updated_pending_product user_id=%s name=%r base=%r stored_after=%s",
            message.from_user.id,
            product.get("name"),
            product.get("base_name"),
            {
                "calories100": product.get("calories100"),
                "protein100": product.get("protein100"),
                "fat100": product.get("fat100"),
                "carbs100": product.get("carbs100"),
                "fiber100": product.get("fiber100"),
            },
        )

        # Show confirmation
        await show_confirmation_interface(message, state)

    except Exception as e:
        logger.error(f"Weight Input Error: {e}", exc_info=True)
        await message.reply(f"❌ Ошибка: {e}")

# --- Helper Functions & New Handlers ---

async def show_confirmation_interface(message: types.Message, state: FSMContext, editable_message: types.Message = None):
    """Show the preview with Confirm/Edit buttons."""
    data = await state.get_data()
    product = data.get("pending_product")

    if not product:
        await message.reply("⚠️ Ошибка контекста.")
        return

    name = product.get('name')
    calories = product.get('calories100', 0) # Use the keys we store
    protein = product.get('protein100', 0)
    fat = product.get('fat100', 0)
    carbs = product.get('carbs100', 0)
    fiber = product.get('fiber100', 0)

    # Check if these are actually totals (from i_ate_process they are just values, mapped to 100 for storage sake?
    # No, in i_ate_process we stored them as calories100 etc in the 'else' block, but as plain vars in the main block.
    # Let's standardize in i_ate_process before calling this function.
    # FIX: i_ate_process needs to save pending_product correctly in the 'happy path' too.
    # Wait, i_ate_process didn't save pending_product in the happy path (lines 122+).
    # I need to fix i_ate_process logic first in the ReplacementChunk above.

    # Standardizing display
    fiber_line = f"\n🥬 Клетчатка: <code>{fiber:.1f}</code>" if fiber else ""
    text = (
        f"<b>🛡️ Проверка данных</b>\n\n"
        f"🍽️ <b>{name}</b>\n\n"
        f"🔥 Ккал: <code>{int(calories)}</code>\n"
        f"🥩 Б: <code>{protein:.1f}</code> | 🥑 Ж: <code>{fat:.1f}</code> | 🍞 У: <code>{carbs:.1f}</code>"
        f"{fiber_line}\n\n"
        f"<blockquote>Всё верно? Нажми «Записать» или отредактируй значения.</blockquote>"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Прямо сейчас", callback_data="i_ate_confirm_now")
    builder.button(text="🕓 Другое время", callback_data="i_ate_ask_time")
    builder.button(text="🍱 Это несколько блюд", callback_data="u_split_to_batch")
    builder.button(text="✏️ Ред. Вес", callback_data="edit_field_weight")
    builder.button(text="✏️ Ред. КБЖУ", callback_data="i_ate_edit_macros")
    builder.button(text="❌ Отмена", callback_data="main_menu")
    builder.adjust(2, 1, 2, 1)

    await state.set_state(IAteStates.waiting_for_confirmation)

    if editable_message:
        await editable_message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())


@router.callback_query(F.data == "i_ate_confirm_now", IAteStates.waiting_for_confirmation)
async def process_confirm_now(callback: types.CallbackQuery, state: FSMContext):
    """Save with current time."""
    await callback.answer()
    await process_save(callback, state, datetime.now())

@router.callback_query(F.data == "i_ate_ask_time", IAteStates.waiting_for_confirmation)
async def ask_time(callback: types.CallbackQuery, state: FSMContext):
    """Show time picker."""
    from utils.time_picker import get_time_picker_keyboard
    await state.set_state(IAteStates.waiting_for_time)
    await callback.message.edit_text(
        "🕓 <b>Когда вы это съели?</b>\n\n"
        "Выберите из пресетов, используйте смещение или <b>введите время текстом</b> (например, <code>12:30</code> или <code>15</code>):",
        parse_mode="HTML",
        reply_markup=get_time_picker_keyboard("i_ate_time")
    )

@router.callback_query(F.data.startswith("i_ate_time:"), IAteStates.waiting_for_time)
async def process_time_selection(callback: types.CallbackQuery, state: FSMContext):
    """Handle time selection."""
    await callback.answer()
    if callback.data == "i_ate_time:back":
        await show_confirmation_interface(callback.message, state)
        return

    from utils.time_picker import get_time_from_callback
    selected_time = get_time_from_callback(callback.data)
    await process_save(callback, state, selected_time)

@router.message(IAteStates.waiting_for_time, F.text)
async def process_manual_time_input(message: types.Message, state: FSMContext):
    """Handle manual text time input."""
    from utils.time_picker import parse_manual_time
    
    selected_time = parse_manual_time(message.text)
    if not selected_time:
        await message.reply(
            "⚠️ <b>Некорректный формат времени</b>\n\n"
            "Пожалуйста, введите время в формате <code>ЧЧ:ММ</code> (например, <code>12:30</code>) "
            "или просто час (например, <code>15</code>).",
            parse_mode="HTML"
        )
        return

    # To use process_save, we need a CallbackQuery-like object or refactor process_save
    # process_save currently expects callback: types.CallbackQuery
    # Let's create a wrapper or refactor process_save to take (user_id, message_to_edit_or_send, state, timestamp)
    
    await process_save_from_message(message, state, selected_time)

async def process_save_from_message(message: types.Message, state: FSMContext, timestamp: datetime):
    """Refactored save logic that works from a regular message."""
    data = await state.get_data()
    product = data.get("pending_product")

    async for session in get_db():
        log = ConsumptionLog(
            user_id=message.from_user.id,
            product_name=product['name'],
            base_name=product.get('base_name'),
            calories=product.get('calories100'),
            protein=product.get('protein100'),
            fat=product.get('fat100'),
            carbs=product.get('carbs100'),
            fiber=product.get('fiber100', 0),
            date=timestamp
        )
        session.add(log)
        await session.commit()

    await state.clear()

    # Format success message
    calories = product.get('calories100', 0)
    protein = product.get('protein100', 0)
    fat = product.get('fat100', 0)
    carbs = product.get('carbs100', 0)
    fiber = product.get('fiber100', 0)

    fiber_line = f"\n🥬 Клетчатка: {fiber:.1f}" if fiber else ""
    # AI Guide Contextual Advice
    guide_comment = ""
    async for session in get_db():
        if await AIGuideService.is_active(message.from_user.id, session):
            current_meal = {
                "name": product['name'],
                "calories": product.get('calories100', 0),
                "protein": product.get('protein100', 0),
                "fat": product.get('fat100', 0),
                "carbs": product.get('carbs100', 0)
            }
            advice = await AIGuideService.get_contextual_advice(message.from_user.id, current_meal, session)
            if advice:
                guide_comment = f"\n\n🤖 <b>Гид:</b> <i>{advice}</i>"
        
        # Track activity for Guide missions
        await AIGuideService.track_activity(message.from_user.id, "log_food", session)
        break

    time_str = timestamp.strftime("%H:%M")
    success_text = (
        f"✅ <b>Записано!</b> ({time_str})\n\n"
        f"🍽️ <b>{product['name']}</b>\n\n"
        f"🔥 <code>{int(calories)}</code> ккал\n"
        f"🥩 <code>{protein:.1f}</code> | 🥑 <code>{fat:.1f}</code> | 🍞 <code>{carbs:.1f}</code>"
        f"{fiber_line}"
        f"{guide_comment}"
    )

    await message.answer(success_text, parse_mode="HTML")

    from services.reports import send_daily_visual_report
    await send_daily_visual_report(message.from_user.id, message.bot)

    # Guide: first-log gift activation
    async for session in get_db():
        logs_count = (await session.execute(
            select(func.count()).select_from(ConsumptionLog).where(ConsumptionLog.user_id == message.from_user.id)
        )).scalar() or 0
        if logs_count == 1 and not await AIGuideService.is_active(message.from_user.id, session):
            builder = InlineKeyboardBuilder()
            builder.button(text="🌸 Поддерживающий", callback_data="first_guide_pers:soft")
            builder.button(text="🦾 Строгий", callback_data="first_guide_pers:hard")
            builder.button(text="📊 Аналитик", callback_data="first_guide_pers:direct")
            builder.adjust(1)
            await message.answer(
                "🤖 <b>Знакомься — твой Личный ИИ-Гид!</b>\n\n"
                "Ты сделал первую запись — и это повод для подарка 🎁\n\n"
                "<b>ИИ-Гид активируется на 3 дня бесплатно.</b>\n\n"
                "После каждого приёма пищи я буду анализировать рацион и давать персональные советы.\n\n"
                "Выбери мой характер:",
                parse_mode="HTML",
                reply_markup=builder.as_markup()
            )
        break

async def process_save(callback: types.CallbackQuery, state: FSMContext, timestamp: datetime):
    # await callback.answer() - Handled by entry point
    """Common save logic."""
    data = await state.get_data()
    product = data.get("pending_product")
    if not product:
        return

    logger.info(
        "KBJU_FLOW i_ate_save about_to_persist user_id=%s ts=%s product_name=%r base=%r saved_kbju={kcal:%s p:%s f:%s c:%s fi:%s}",
        callback.from_user.id,
        timestamp,
        product.get("name") if isinstance(product, dict) else None,
        product.get("base_name") if isinstance(product, dict) else None,
        (product or {}).get("calories100") if isinstance(product, dict) else None,
        (product or {}).get("protein100") if isinstance(product, dict) else None,
        (product or {}).get("fat100") if isinstance(product, dict) else None,
        (product or {}).get("carbs100") if isinstance(product, dict) else None,
        (product or {}).get("fiber100") if isinstance(product, dict) else None,
    )

    async for session in get_db():
        log = ConsumptionLog(
            user_id=callback.from_user.id,
            product_name=product['name'],
            base_name=product.get('base_name'),
            calories=product.get('calories100'),
            protein=product.get('protein100'),
            fat=product.get('fat100'),
            carbs=product.get('carbs100'),
            fiber=product.get('fiber100', 0),
            date=timestamp
        )
        session.add(log)
        await session.commit()

    await state.clear()

    # Format success message with full details
    calories = product.get('calories100', 0)
    protein = product.get('protein100', 0)
    fat = product.get('fat100', 0)
    carbs = product.get('carbs100', 0)
    fiber = product.get('fiber100', 0)

    fiber_line = f"\n🥬 Клетчатка: {fiber:.1f}" if fiber else ""
    time_str = timestamp.strftime("%H:%M")
    success_text = (
        f"✅ <b>Записано!</b> ({time_str})\n\n"
        f"🍽️ <b>{product['name']}</b>\n\n"
        f"🔥 <code>{int(calories)}</code> ккал\n"
        f"🥩 {protein:.1f} | 🥑 {fat:.1f} | 🍞 {carbs:.1f}"
        f"{fiber_line}"
    )

    await callback.message.edit_text(success_text, parse_mode="HTML")

    # NEW: Send visual progress card
    from services.reports import send_daily_visual_report
    await send_daily_visual_report(callback.from_user.id, callback.bot)

    # 5. Guide: first-log gift activation OR regular advice
    async for session in get_db():
        logs_count = (await session.execute(
            select(func.count()).select_from(ConsumptionLog).where(ConsumptionLog.user_id == callback.from_user.id)
        )).scalar() or 0
        guide_active = await AIGuideService.is_active(callback.from_user.id, session)

        if logs_count == 1 and not guide_active:
            builder = InlineKeyboardBuilder()
            builder.button(text="🌸 Поддерживающий", callback_data="first_guide_pers:soft")
            builder.button(text="🦾 Строгий", callback_data="first_guide_pers:hard")
            builder.button(text="📊 Аналитик", callback_data="first_guide_pers:direct")
            builder.adjust(1)
            await callback.message.answer(
                "🤖 <b>Знакомься — твой Личный ИИ-Гид!</b>\n\n"
                "Ты сделал первую запись — и это повод для подарка 🎁\n\n"
                "<b>ИИ-Гид активируется на 3 дня бесплатно.</b>\n\n"
                "После каждого приёма пищи я буду анализировать рацион и давать персональные советы.\n\n"
                "Выбери мой характер:",
                parse_mode="HTML",
                reply_markup=builder.as_markup()
            )
        elif guide_active:
            current_meal = {
                "name": product['name'],
                "calories": product.get('calories100', 0),
                "protein": product.get('protein100', 0),
                "fat": product.get('fat100', 0),
                "carbs": product.get('carbs100', 0),
                "time": timestamp.strftime("%H:%M")
            }
            advice = await AIGuideService.get_contextual_advice(callback.from_user.id, current_meal, session)
            if advice:
                await callback.message.answer(f"🤖 <b>Гид:</b> <i>{advice}</i>", parse_mode="HTML")

        await AIGuideService.track_activity(callback.from_user.id, "log_food", session)
        break

    # await callback.answer() - Removed
@router.callback_query(F.data == "edit_field_weight", IAteStates.waiting_for_confirmation)
async def start_edit_weight(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(IAteStates.waiting_for_weight) # Reuse existing logic
    await callback.message.edit_text("⚖️ Введите новый вес (числом):")

@router.callback_query(F.data == "i_ate_edit_macros", IAteStates.waiting_for_confirmation)
async def start_edit_macros(callback: types.CallbackQuery, state: FSMContext):
    builder = InlineKeyboardBuilder()
    builder.button(text="🔥 Ккал", callback_data="edit_macro_calories100")
    builder.button(text="🥩 Белки", callback_data="edit_macro_protein100")
    builder.button(text="🥑 Жиры", callback_data="edit_macro_fat100")
    builder.button(text="🍞 Углеводы", callback_data="edit_macro_carbs100")
    builder.button(text="🥬 Клетчатка", callback_data="edit_macro_fiber100")
    builder.button(text="🔙 Назад", callback_data="back_to_confirm")
    builder.adjust(2, 3, 1)

    await callback.message.edit_text("👇 Что меняем?", reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("edit_macro_"))
async def ask_macro_value(callback: types.CallbackQuery, state: FSMContext):
    field = callback.data.split("macro_")[1]
    await state.update_data(current_edit_field=field)
    await state.set_state(IAteStates.waiting_for_edit_value)

    labels = {
        "calories100": "Калории", "protein100": "Белки",
        "fat100": "Жиры", "carbs100": "Углеводы", "fiber100": "Клетчатку"
    }

    await callback.message.edit_text(f"✏️ Введите новое значение для <b>{labels.get(field)}</b>:", parse_mode="HTML")

@router.message(IAteStates.waiting_for_edit_value)
async def save_macro_value(message: types.Message, state: FSMContext):
    try:
        value = float(message.text.split()[0].replace(',', '.'))
        data = await state.get_data()
        field = data.get("current_edit_field")
        product = data.get("pending_product")

        product[field] = value
        await state.update_data(pending_product=product)

        await show_confirmation_interface(message, state)

    except ValueError:
        await message.reply("⚠️ Введите число.")

@router.callback_query(F.data == "back_to_confirm")
async def back_to_confirm_handler(callback: types.CallbackQuery, state: FSMContext):
    await show_confirmation_interface(callback.message, state)


# Маппинг коротких кодов → описания для AI (callback_data не более 64 байт)
_QUICK_FOOD_ITEMS = {
    "1": "яичница",
    "2": "бутерброд с докторской колбасой",
    "3": "овсяная каша на молоке",
    "4": "творог",
}

# Умный выбор порции — никаких граммов вручную
_PORTION_HINTS = [
    ("яичниц",    "Из скольких яиц?",    [("1 яйцо", 55),   ("2 яйца", 110),  ("3 яйца", 165)]),
    ("омлет",     "Из скольких яиц?",    [("1 яйцо", 65),   ("2 яйца", 130),  ("3 яйца", 195)]),
    ("бутерброд", "Сколько бутербродов?",[("1 шт",    80),   ("2 шт",   160),  ("3 шт",   240)]),
    ("блин",      "Сколько блинов?",     [("1 блин",  60),   ("2 блина", 120), ("3 блина", 180)]),
    ("каш",       "Размер порции?",      [("Маленькая ~150г", 150), ("Стандарт ~200г", 200), ("Большая ~300г", 300)]),
    ("творог",    "Сколько творога?",    [("100г", 100), ("150г", 150), ("200г", 200)]),
    ("сырник",    "Сколько сырников?",   [("1 шт", 60),  ("2 шт", 120),  ("3 шт", 180)]),
]
_DEFAULT_PORTIONS = ("Размер порции?", [("Небольшая ~100г", 100), ("Средняя ~200г", 200), ("Большая ~300г", 300)])


def _get_portion_options(food_name: str):
    name_lower = food_name.lower()
    for keyword, question, options in _PORTION_HINTS:
        if keyword in name_lower:
            return question, options
    return _DEFAULT_PORTIONS


@router.callback_query(F.data.startswith("quick_food:"))
async def quick_food_select(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Handle quick food selection from first-timer screen."""
    code = callback.data.split(":", 1)[1]
    food_description = _QUICK_FOOD_ITEMS.get(code, code)
    await callback.answer()

    status_msg = await callback.message.answer("🔄 <b>Анализирую...</b>", parse_mode="HTML")

    try:
        from services.ai_brain import AIBrainService
        brain_result = await AIBrainService.analyze_text(food_description)

        if brain_result and isinstance(brain_result, dict) and brain_result.get("multi") and brain_result.get("items"):
            items = brain_result["items"]
            if len(items) > 1:
                from handlers.universal_input import process_batch_food_logging
                await process_batch_food_logging(callback.message, state, items, status_msg)
                return

        result = await NormalizationService.analyze_food_intake(food_description)

        name = result.get("name", food_description)
        calories = safe_float(result.get("calories"))
        protein = safe_float(result.get("protein"))
        fat = safe_float(result.get("fat"))
        carbs = safe_float(result.get("carbs"))
        fiber = safe_float(result.get("fiber"))
        weight_grams = result.get("weight_grams")
        weight_missing = result.get("weight_missing", True)
        base_name = result.get("base_name")

        if weight_missing:
            await state.update_data(
                pending_product={
                    "name": name,
                    "base_name": base_name,
                    "calories100": calories,
                    "protein100": protein,
                    "fat100": fat,
                    "carbs100": carbs,
                    "fiber100": fiber,
                    "original_text": food_description,
                }
            )

            question, portions = _get_portion_options(name)
            builder = InlineKeyboardBuilder()
            for label, weight in portions:
                builder.button(text=label, callback_data=f"quick_portion:{weight}")
            builder.button(text="❌ Отмена", callback_data="main_menu")
            builder.adjust(len(portions), 1)

            await status_msg.edit_text(
                f"🍽️ <b>{name}</b>\n\n{question}",
                parse_mode="HTML",
                reply_markup=builder.as_markup()
            )
            return

        await state.update_data(
            pending_product={
                "name": f"{name} ({weight_grams}г)",
                "base_name": base_name,
                "calories100": calories,
                "protein100": protein,
                "fat100": fat,
                "carbs100": carbs,
                "fiber100": fiber,
                "original_text": food_description,
            }
        )
        await show_confirmation_interface(callback.message, state, status_msg)

    except Exception as e:
        logger.error(f"Error in quick_food_select: {e}", exc_info=True)
        await state.clear()
        await status_msg.edit_text(f"❌ Ошибка: {e}\n\nПопробуйте ещё раз.")


@router.callback_query(F.data.startswith("quick_portion:"))
async def quick_portion_select(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Apply chosen portion weight to pending product and show confirmation."""
    weight = float(callback.data.split(":", 1)[1])
    await callback.answer()

    data = await state.get_data()
    product = data.get("pending_product")
    if not product:
        await callback.answer("Попробуйте снова", show_alert=True)
        return

    factor = weight / 100.0
    display_name = product.get("base_name") or product.get("name", "")
    product["name"] = f"{display_name} ({int(weight)}г)"
    product["calories100"] = safe_float(product.get("calories100")) * factor
    product["protein100"] = safe_float(product.get("protein100")) * factor
    product["fat100"] = safe_float(product.get("fat100")) * factor
    product["carbs100"] = safe_float(product.get("carbs100")) * factor
    product["fiber100"] = safe_float(product.get("fiber100", 0)) * factor

    await state.update_data(pending_product=product)
    await show_confirmation_interface(callback.message, state)


@router.callback_query(F.data == "i_ate_manual")
async def i_ate_manual(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Switch from first-timer quick buttons to standard text input."""
    await callback.answer()

    builder = InlineKeyboardBuilder()
    builder.button(text="🏗️ Собрать блюдо", callback_data="menu_build_dish")
    builder.button(text="❌ Отмена", callback_data="main_menu")
    builder.adjust(1)

    caption = (
        "🍽️ <b>Что съели?</b>\n\n"
        "Напишите что вы съели — можно с весом или без:\n\n"
        "<i>Например:\n"
        "• Борщ 300г\n"
        "• Куриная грудка\n"
        "• 2 яйца</i>"
    )

    photo_path = types.FSInputFile("assets/i_ate.png")
    try:
        await callback.message.edit_media(
            media=types.InputMediaPhoto(media=photo_path, caption=caption, parse_mode="HTML"),
            reply_markup=builder.as_markup()
        )
    except Exception:
        await callback.message.answer(caption, parse_mode="HTML", reply_markup=builder.as_markup())


@router.callback_query(F.data == "first_log_later")
async def first_log_later(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Dismiss first-log nudge from scheduler."""
    await callback.answer("Хорошо! Заходи когда будешь готов 😊", show_alert=False)
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
