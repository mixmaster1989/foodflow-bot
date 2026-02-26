"""Module for universal input handling (Text, Photo, Voice).

Unified entry point for:
- Text messages
- Voice messages (STT)
- Photos

Provides a single menu for user actions:
- I Ate -> ConsumptionLog
- To Fridge -> Product
- Receipt -> Receipt Processing
- Price Tag -> Price Tag Processing
"""
import logging
import os
from datetime import datetime

from aiogram import Bot, F, Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from database.base import get_db
from database.models import ConsumptionLog, Product, SavedDish
from handlers.i_ate import show_confirmation_interface
from services.ai_brain import AIBrainService
from services.herbalife_expert import herbalife_expert
from services.normalization import NormalizationService
from services.voice_stt import SpeechToText
from utils.parsing import safe_float

router = Router()
logger = logging.getLogger(__name__)
stt_engine = SpeechToText()

class UniversalInputStates(StatesGroup):
    action_pending = State()      # Waiting for user to choose action
    waiting_for_weight = State()  # Waiting for weight input
    waiting_for_product_name = State() # Waiting for product name clarification
    waiting_for_intent = State()   # Waiting for intent clarification
    waiting_for_quantity = State() # NEW: Waiting for quantity (pieces) input
    batch_confirmation = State()  # Viewing batch list
    batch_editing = State()       # Editing individual item in batch
    batch_time_selection = State() # Selecting time for the whole batch
    batch_waiting_for_macro_value = State() # Waiting for KBJU value input

# --- HANDLERS ---

@router.message(F.voice)
async def handle_voice(message: types.Message, bot: Bot, state: FSMContext, user_tier: str = "free") -> None:
    """Handle voice messages with STT."""

    if user_tier == "free":
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        builder.button(text="💎 Подробнее о подписках", callback_data="show_subscriptions")
        await message.reply(
            "🎙️ <b>Голосовой ввод недоступен</b>\n\n"
            "Функция доступна начиная с подписки <b>Basic</b>.\n"
            "Оформите подписку, чтобы диктовать еду голосом и экономить время!",
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
        return

    current_state = await state.get_state()
    if current_state:
        # If in a specific state (e.g. adding receipt items), ignore voice or handle differently?
        # For now, let's treat it as new input if it's a global state,
        # but maybe we should warn user if they are in the middle of something.
        # Let's try to process it anyway as universal input.
        pass

    status_msg = await message.reply("🎤 Слушаю...")

    try:
        # Download voice file
        file_info = await bot.get_file(message.voice.file_id)

        # Create temp path
        temp_dir = "services/temp"
        os.makedirs(temp_dir, exist_ok=True)
        ogg_path = f"{temp_dir}/voice_{message.voice.file_id}.ogg"

        await bot.download_file(file_info.file_path, ogg_path)

        # Transcribe
        text = await stt_engine.process_voice_message(ogg_path)

        # Cleanup
        try:
            os.remove(ogg_path)
        except Exception:
            pass

        if not text:
            await status_msg.edit_text("❌ Не удалось распознать речь.")
            return

        # Delegate to common processor
        await process_universal_input(message, "voice", text, state, status_msg)

    except Exception as e:
        logger.error(f"Voice Error: {e}", exc_info=True)
        await status_msg.edit_text(f"<b>❌ Ошибка:</b> <code>{e}</code>")


@router.message(F.photo, StateFilter(None))
async def handle_photo(message: types.Message, state: FSMContext, user_tier: str = "free") -> None:
    """Handle photos when no specific state is active. Auto-analyze content."""

    if user_tier in ["free", "basic"]:
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        builder.button(text="💎 Подробнее о подписках", callback_data="show_subscriptions")
        await message.reply(
            "📸 <b>Распознавание фото недоступно</b>\n\n"
            "Функция доступна только в подписке <b>Pro</b>.\n"
            "Оформите подписку, чтобы ИИ распознавал еду и чеки по картинке!",
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
        return

    status_msg = await message.reply("👀 <b>Смотрю, что на фото...</b>", parse_mode="HTML")

    try:
        # 1. Analyze via Vision
        description = await AIBrainService.analyze_image(message, prompt="Что на фото? Если это еда или продукты, напиши название и вкус. Если чек - напиши 'чек'.")

        logger.info(f"📸 Photo Analysis Result: '{description}'")

        if not description:
             await status_msg.edit_text("❌ Не удалось понять, что на фото.")
             return

        # 2. Update status
        await status_msg.edit_text(f"👀 <b>Вижу:</b> <blockquote>{description[:50]}...</blockquote>", parse_mode="HTML")

        # 3. Process as text input
        # Combine caption if exists
        full_content = f"{description}"
        if message.caption:
            full_content = f"{message.caption} . На фото: {description}"

        await process_universal_input(message, "text", full_content, state, status_msg) # Treat as text now!

    except Exception as e:
        logger.error(f"Photo Analysis Error: {e}", exc_info=True)
        await status_msg.edit_text(f"<b>❌ Ошибка анализа:</b> <code>{e}</code>")


@router.message(F.text, StateFilter(None))
async def handle_text(message: types.Message, state: FSMContext) -> None:
    """Handle text messages when no state is active."""
    # Ignore commands
    if message.text.startswith("/"):
        return

    if len(message.text) < 2:
        return

    await process_universal_input(message, "text", message.text, state)


# --- CORE PROCESSOR ---

async def process_universal_input(
    message: types.Message,
    input_type: str,
    content: str,
    state: FSMContext,
    status_msg: types.Message = None
) -> None:
    """Common logic for showing action menu OR auto-executing brain commands."""

    # AI BRAIN PROCESSOR (If text/voice detected)
    if input_type in ("text", "voice") and content and len(content) > 3:
        if status_msg:
             await status_msg.edit_text(f"🧠 <b>Думаю:</b> <blockquote>{content}</blockquote>", parse_mode="HTML")
        else:
             status_msg = await message.reply(f"🧠 <b>Думаю:</b> <blockquote>{content}</blockquote>", parse_mode="HTML")

        brain_result = await AIBrainService.analyze_text(content)
        is_herbalife = await herbalife_expert.find_product_by_alias(content)

        # --- SMART FORK: Multi-item vs Single-item ---
        if brain_result and not is_herbalife:
            # Case 1: AI returned a dict with multi=true and items array
            if isinstance(brain_result, dict) and brain_result.get("multi") and brain_result.get("items"):
                items = brain_result["items"]
                if len(items) > 1:
                    await process_batch_food_logging(message, state, items, status_msg)
                    return
                # If somehow only 1 item in multi, treat as single
                elif len(items) == 1:
                    brain_result = {
                        "intent": brain_result.get("intent", "log_consumption"),
                        "product": items[0].get("product"),
                        "weight": items[0].get("weight")
                    }

            # Case 2: AI returned a raw list (legacy bug)
            if isinstance(brain_result, list) and len(brain_result) > 1:
                items = [{"product": item.get("product") or item.get("name", ""), "weight": item.get("weight")} for item in brain_result if isinstance(item, dict)]
                if items:
                    await process_batch_food_logging(message, state, items, status_msg)
                    return

            # Case 3: Normal single-item dict
            if isinstance(brain_result, dict) and brain_result.get("intent") in ["log_consumption", "add_to_fridge"]:
                intent = brain_result["intent"]
                product = brain_result.get("product") or content
                weight = brain_result.get("weight")

                if weight:
                    try:
                        weight = float(weight)
                    except Exception:
                        weight = None

                if intent == "log_consumption":
                    await process_text_food_logging(message, state, product, weight_override=weight, status_msg=status_msg)
                    return
                elif intent == "add_to_fridge":
                    await process_text_fridge_add(message, state, product, weight_override=weight, status_msg=status_msg)
                    return

    # Fallback to Menu (Classic Mode with Voice Support)

    # Save context
    # We use 'action_pending' which will now support Voice replies too!
    await state.set_state(UniversalInputStates.action_pending)

    # Context data
    data = {
        "input_type": input_type,
        "content": content,
        "timestamp": datetime.now().isoformat()
    }

    # If photo, save file_id
    if input_type == "photo":
        data["file_id"] = message.photo[-1].file_id

    await state.update_data(universal_data=data)

    builder = InlineKeyboardBuilder()

    # Core Actions
    builder.button(text="🍽️ Я съел(а)", callback_data="u_action_ate")
    builder.button(text="🧊 В холодильник", callback_data="u_action_fridge")
    builder.button(text="🌿 Это Гербалайф", callback_data="u_action_herbalife")

    # Photo-specific Actions
    if input_type == "photo":
        builder.button(text="🧾 Это чек", callback_data="u_action_receipt")
        builder.button(text="🏷️ Ценник", callback_data="u_action_pricetag")

    builder.button(text="❌ Отмена", callback_data="u_action_cancel")

    # Layout
    if input_type == "photo":
        builder.adjust(2, 1, 2, 1) # Ate/Fridge, Herbalife, Receipt/Price, Cancel
    else:
        builder.adjust(2, 1, 1)    # Ate/Fridge, Herbalife, Cancel

    text_preview = f"<blockquote>{content}</blockquote>" if content else ""
    header = "🤔 <b>Я не понял намерение.</b>\nСкажите: <i>\"Я съел\"</i> или <i>\"В холодильник\"</i>"

    if input_type == "voice":
        header = "🎤 <b>Голос распознан:</b>"
    elif input_type == "photo":
        header = "📸 <b>Фото получено:</b>"

    # Update header if it was just Unknown intent from Brain
    if input_type in ("text", "voice") and content:
         header = "🤔 <b>Я понял продукт, но не понял что сделать.</b>"

    msg_text = (
        f"{header}\n\n"
        f"{text_preview}\n\n"
        "👇 <b>Выберите действие или скажите голосом:</b>"
    )

    if status_msg:
        await status_msg.edit_text(msg_text, parse_mode="HTML", reply_markup=builder.as_markup())
    else:
        await message.reply(msg_text, parse_mode="HTML", reply_markup=builder.as_markup())


# --- INTENT CLARIFICATION HANDLERS (Action Pending) ---

@router.message(UniversalInputStates.action_pending, F.voice)
async def handle_action_pending_voice(message: types.Message, bot: Bot, state: FSMContext) -> None:
    """Handle intent clarification via voice."""
    status_msg = await message.reply("🎤 Определяю намерение...")

    try:
        file_info = await bot.get_file(message.voice.file_id)
        temp_dir = "services/temp"
        os.makedirs(temp_dir, exist_ok=True)
        ogg_path = f"{temp_dir}/intent_{message.voice.file_id}.ogg"
        await bot.download_file(file_info.file_path, ogg_path)

        text = await stt_engine.process_voice_message(ogg_path)
        try:
            os.remove(ogg_path)
        except Exception:
            pass

        if not text:
            await status_msg.edit_text("❌ Не удалось распознать. Выберите кнопку.")
            return

        text = text.lower()
        data = await state.get_data()
        uni_data = data.get("universal_data", {})
        content = uni_data.get("content")
        input_type = uni_data.get("input_type")

        # 1. Herbalife Shortcut
        if any(w in text for w in ["гербалайф", "herbalife", "база", "эксперт"]):
             await process_herbalife_input(message, state, content, status_msg=status_msg)
             return

        # 2. Simple keywords
        if any(w in text for w in ["съел", "ел", "кушал", "обед", "ужин", "завтрак", "ate", "eat"]):
            if input_type == "photo":
                await process_photo_food_logging(message, state, uni_data["file_id"]) # Logic needs verify for status_msg pass
            else:
                await process_text_food_logging(message, state, content, status_msg=status_msg)

        elif any(w in text for w in ["холодильник", "купил", "магазин", "fridge", "buy"]):
            if input_type == "photo":
                 await process_photo_fridge_add(message, state, uni_data["file_id"])
            else:
                 await process_text_fridge_add(message, state, content, status_msg=status_msg)
        else:
             await status_msg.edit_text("🤔 Не понял. Скажите 'Съел', 'Гербалайф' или 'В холодильник'.")

    except Exception as e:
        logger.error(f"Intent Voice Error: {e}")
        await status_msg.edit_text("❌ Ошибка.")


# --- CALLBACKS ---

@router.callback_query(F.data == "u_action_cancel")
async def universal_cancel(callback: types.CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.delete()
    await callback.answer("Отменено")


@router.callback_query(UniversalInputStates.action_pending, F.data == "u_action_ate")
async def universal_action_ate(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Handle 'I Ate' action."""
    data = await state.get_data()
    uni_data = data.get("universal_data", {})
    input_type = uni_data.get("input_type")
    content = uni_data.get("content")

    if input_type == "photo":
        # Redirect to receipt logic (log single food photo)
        # We need to manually trigger the logic from receipt.py or replicate it.
        # Ideally, we call a service or shared function.
        # For MVP: Let's call the receipt handler logic manually or simulate the call?
        # Better: Import the logic.

        # Let's reuse ReceiptStates logic from receipt.py?
        # Actually, receipt.py listens for F.data == "action_log_food"
        # We can artificially create that call, but it relies on reply_to_message being the photo.
        # In universal input, message structure might be different.

        # Let's use AIService directly here for cleaner architecture.
        await process_photo_food_logging(callback, state, uni_data["file_id"])

    else:
        # Text/Voice -> Text Processing
        if not content:
            await callback.answer("⚠️ Нет текста для анализа.", show_alert=True)
            return

        await process_text_food_logging(callback, state, content)


@router.callback_query(UniversalInputStates.action_pending, F.data == "u_action_fridge")
async def universal_action_fridge(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Handle 'To Fridge' action."""
    data = await state.get_data()
    uni_data = data.get("universal_data", {})
    input_type = uni_data.get("input_type")
    content = uni_data.get("content")

    if input_type == "photo":
         await process_photo_fridge_add(callback, state, uni_data["file_id"])
    else:
         if not content:
            await callback.answer("⚠️ Нет текста.", show_alert=True)
            return
         await process_text_fridge_add(callback, state, content)


@router.callback_query(UniversalInputStates.action_pending, F.data == "u_action_herbalife")
async def universal_action_herbalife(callback: types.CallbackQuery, state: FSMContext):
    """Handle 'Herbalife' action."""
    data = await state.get_data()
    uni_data = data.get("universal_data", {})
    content = uni_data.get("content")

    await process_herbalife_input(callback, state, content)



@router.callback_query(UniversalInputStates.action_pending, F.data == "u_action_receipt")
async def universal_action_receipt(callback: types.CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Handle 'Receipt' action (Photo only)."""
    data = await state.get_data()
    uni_data = data.get("universal_data", {})
    file_id = uni_data.get("file_id")

    if not file_id:
        await callback.answer("❌ Ошибка: нет фото.", show_alert=True)
        return

    # Clear state here, as receipt processing uses its own queue/flow
    await state.clear()

    await callback.message.edit_text("⏳ Добавляю чек в очередь...")

    from handlers.receipt import process_receipt_worker_action
    from services.photo_queue import PhotoQueueManager

    # We need to mock a message structure that PhotoQueue expects
    # It expects message to be the one to edit.

    await PhotoQueueManager.add_item(
        user_id=callback.from_user.id,
        message=callback.message,
        bot=bot,
        state=state,
        processing_func=process_receipt_worker_action,
        file_id=file_id
    )
    await callback.answer()


@router.callback_query(UniversalInputStates.action_pending, F.data == "u_action_pricetag")
async def universal_action_pricetag(callback: types.CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Handle 'Price Tag' action (Photo only)."""
    data = await state.get_data()
    uni_data = data.get("universal_data", {})
    file_id = uni_data.get("file_id")

    if not file_id:
        await callback.answer("❌ Ошибка: нет фото.", show_alert=True)
        return

    await state.clear()
    await callback.message.edit_text("⏳ Анализирую ценник...")

    # Reuse Logic from receipt.py price_tag_action
    # But implement here to avoid circular imports or complex deps
    try:
        import io

        from database.models import PriceTag
        from services.price_tag_ocr import PriceTagOCRService

        file_info = await bot.get_file(file_id)
        photo_bytes = io.BytesIO()
        await bot.download_file(file_info.file_path, photo_bytes)

        price_data = await PriceTagOCRService.parse_price_tag(photo_bytes.getvalue())

        if not price_data or not price_data.get("product_name") or not price_data.get("price"):
            await callback.message.edit_text("❌ Не удалось распознать ценник.")
            return

        async for session in get_db():
            price_tag = PriceTag(
                user_id=callback.from_user.id,
                product_name=price_data.get("product_name"),
                volume=price_data.get("volume"),
                price=float(price_data.get("price")),
                store_name=price_data.get("store"),
                photo_date=datetime.fromisoformat(price_data["date"]) if price_data.get("date") else None,
            )
            session.add(price_tag)
            await session.commit()
            break

        await callback.message.edit_text(f"✅ Ценник сохранен: {price_data.get('product_name')} - {price_data.get('price')}р")

    except Exception as e:
        logger.error(f"PriceTag Error: {e}")
        await callback.message.edit_text(f"❌ Ошибка: {e}")

@router.callback_query(F.data == "u_mode_qty")
async def switch_to_quantity_mode(callback: types.CallbackQuery, state: FSMContext):
    """Switch input mode to Pieces (Quantity)."""
    data = await state.get_data()
    product = data.get("pending_product")
    if not product:
        await callback.answer("⚠️ Ошибка контекста", show_alert=True)
        return

    await state.set_state(UniversalInputStates.waiting_for_quantity)

    builder = InlineKeyboardBuilder()
    builder.button(text="⚖️ В граммы", callback_data="u_mode_weight")
    builder.button(text="❌ Отмена", callback_data="u_action_cancel")
    builder.adjust(1, 1)

    await callback.message.edit_text(
        f"📦 <b>{product['name']}</b>\n\n"
        f"🔢 <b>Сколько штук?</b> (Напишите число)",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )

@router.callback_query(F.data == "u_mode_weight")
async def switch_to_weight_mode(callback: types.CallbackQuery, state: FSMContext):
    """Switch input mode back to Grams (Weight)."""
    data = await state.get_data()
    product = data.get("pending_product")
    if not product:
        await callback.answer("⚠️ Ошибка контекста", show_alert=True)
        return

    await state.set_state(UniversalInputStates.waiting_for_weight)

    builder = InlineKeyboardBuilder()
    builder.button(text="🔢 В штуках", callback_data="u_mode_qty")
    builder.button(text="❌ Отмена", callback_data="u_action_cancel")
    builder.adjust(1, 1)

    await callback.message.edit_text(
        f"🧐 <b>{product['name']}</b>\n\n"
        f"⚖️ <b>Сколько грамм?</b> (Напишите число)",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )

@router.message(UniversalInputStates.waiting_for_quantity, F.text)
async def handle_quantity_input(message: types.Message, state: FSMContext) -> None:
    """Handle quantity input (e.g. '2') and convert to weight via AI."""
    try:
        # 1. Parse number
        text = message.text.replace(',', '.').strip()
        import re
        match = re.search(r'(\d+(?:\.\d+)?)', text)
        if not match:
            await message.reply("⚠️ Пожалуйста, введите число (количество штук).")
            return

        quantity = float(match.group(1))

        # 2. Get context
        data = await state.get_data()
        product = data.get("pending_product")
        intent = data.get("intent", "log") # Default to log if missing

        status_msg = await message.answer(f"🔄 Считаю вес для <code>{quantity} шт</code>...")

        # 3. Ask AI to re-normalize "Quantity + Name"
        # query = "2 Яйцо куриное"
        query = f"{quantity} {product['base_name'] or product['name']}"

        # We reuse NormalizationService.analyze_food_intake
        result = await NormalizationService.analyze_food_intake(query)

        # 4. Update Product Data
        weight_grams = result.get("weight_grams")

        if not weight_grams:
            await status_msg.edit_text("⚠️ Не удалось определить вес. Пожалуйста, введите вес в граммах вручную.")
            await state.set_state(UniversalInputStates.waiting_for_weight)
            return

        # Update product with new calculated values
        product['name'] = f"{product['base_name']} ({quantity} шт / ~{weight_grams}г)"
        product['calories100'] = float(result.get("calories", 0))
        product['protein100'] = float(result.get("protein", 0))
        product['fat100'] = float(result.get("fat", 0))
        product['carbs100'] = float(result.get("carbs", 0))
        product['fiber100'] = float(result.get("fiber", 0))

        # IMPORTANT: Store calculated total weight too if needed,
        # but our DB model stores 'weight_g' for the product.
        # The 'product' dict keys (calories100, etc) usually mean TOTAL in the final step
        # (see i_ate.py:195 -> show_confirmation_interface uses them as totals).
        # Let's verify NormalizationService output.
        # analyze_food_intake returns TOTAL KBJU for the weight.
        # So we just drop them into the '100' keys (naming is legacy confusion, but logic holds).

        await state.update_data(pending_product=product)

        # 5. Route to Confirmation or Fridge
        if intent == "fridge":
            # For fridge we need to finalize the object
            async for session in get_db():
                db_product = Product(
                    user_id=message.from_user.id,
                    name=product['name'],
                    category="Manual",
                    calories=product['calories100'],
                    protein=product['protein100'],
                    fat=product['fat100'],
                    carbs=product['carbs100'],
                    fiber=product['fiber100'],
                    price=0.0,
                    quantity=quantity, # Store pieces count!
                    weight_g=float(weight_grams),
                    source="universal_qty"
                )
                session.add(db_product)
                await session.commit()
                product_id = db_product.id

            await state.clear()

            builder = InlineKeyboardBuilder()
            builder.button(text="🍽️ Нет, я это съел(а)", callback_data=f"u_move_to_ate:{product_id}")

            await status_msg.edit_text(
                f"✅ <b>Добавлено в холодильник:</b>\n"
                f"📦 {product['name']}\n"
                f"⚖️ Вес: ~{weight_grams}г",
                parse_mode="HTML",
                reply_markup=builder.as_markup()
            )

        else:
            # Intent is "log" (I ate)
            await show_confirmation_interface(message, state, status_msg)

    except Exception as e:
        logger.error(f"Quantity Input Error: {e}", exc_info=True)
        await message.reply(f"❌ Ошибка: {e}")

@router.callback_query(F.data.startswith("u_move_to_ate:"))
async def move_from_fridge_to_ate(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Correct mistake: move product from fridge to consumption log."""
    product_id = int(callback.data.split(":")[1])

    async for session in get_db():
        product = await session.get(Product, product_id)
        if not product:
            await callback.answer("❌ Продукт не найден (возможно, уже удален).", show_alert=True)
            return

        product_name = product.name
        weight = product.weight_g

        # Delete from fridge
        await session.delete(product)
        await session.commit()

    await callback.answer("🔄 Переношу в лог питания...")

    # Redirect to food logging logic
    # We use process_text_food_logging which will show KBJU confirmation
    await process_text_food_logging(callback, state, product_name, weight_override=weight)


@router.message(UniversalInputStates.waiting_for_weight, F.text)
async def handle_universal_weight_input(message: types.Message, state: FSMContext) -> None:
    """Handle weight input for Universal Input flows."""
    try:
        weight_text = message.text.replace(',', '.').strip()
        import re
        match = re.search(r'(\d+(?:\.\d+)?)', weight_text)

        if not match:
            await message.reply("⚠️ Пожалуйста, введите только число (вес в граммах).")
            return

        weight = float(match.group(1))

        data = await state.get_data()
        product = data.get("pending_product")
        pending_water = data.get("pending_water")
        intent = data.get("intent", "log")

        if pending_water:
            amount_ml = int(weight)
            from database.models import WaterLog
            async for session in get_db():
                log = WaterLog(
                    user_id=message.from_user.id,
                    amount_ml=amount_ml
                )
                session.add(log)
                await session.commit()

            await message.answer(f"✅ Добавлено {amount_ml} мл воды!")
            await state.clear()

            from handlers.menu import show_main_menu
            await show_main_menu(message, message.from_user.first_name, message.from_user.id)
            return

        if not product:
            await message.reply("⚠️ Ошибка контекста.")
            await state.clear()
            return

        # Recalculate based on weight
        factor = weight / 100.0

        product['name'] = f"{product['base_name']} ({int(weight)}г)"
        product['calories100'] = product['calories100'] * factor
        product['protein100'] = product['protein100'] * factor
        product['fat100'] = product['fat100'] * factor
        product['carbs100'] = product['carbs100'] * factor
        product['fiber100'] = product['fiber100'] * factor

        await state.update_data(pending_product=product)

        if intent == "fridge":
             async for session in get_db():
                db_product = Product(
                    user_id=message.from_user.id,
                    name=product['name'],
                    category="Manual",
                    calories=product['calories100'],
                    protein=product['protein100'],
                    fat=product['fat100'],
                    carbs=product['carbs100'],
                    fiber=product['fiber100'],
                    price=0.0,
                    quantity=1.0,
                    weight_g=weight,
                    source="universal_weight"
                )
                session.add(db_product)
                await session.commit()
                product_id = db_product.id

             await state.clear()
             builder = InlineKeyboardBuilder()
             builder.button(text="🍽️ Нет, я это съел(а)", callback_data=f"u_move_to_ate:{product_id}")

             await message.answer(
                f"✅ <b>Добавлено в холодильник:</b>\n"
                f"📦 {product['name']}",
                parse_mode="HTML",
                reply_markup=builder.as_markup()
             )
        else:
             # Log intent
             await show_confirmation_interface(message, state)

    except Exception as e:
        logger.error(f"Universal Weight Input Error: {e}", exc_info=True)
        await message.reply(f"❌ Ошибка: {e}")

# --- HELPERS --

async def process_text_food_logging(
    target: types.CallbackQuery | types.Message,
    state: FSMContext,
    text: str,
    weight_override: float | None = None,
    status_msg: types.Message | None = None
):
    """Log food from text (Similar to i_ate.py)."""
    user_id = target.from_user.id

    # Determine message to update/reply
    if status_msg:
        msg = status_msg
    elif isinstance(target, types.CallbackQuery):
        msg = target.message
    else:
        # target is user message, so we must reply
        msg = await target.answer(f"🔄 Анализирую: <i>{text}</i>...", parse_mode="HTML")

    # Try to edit if it's our message (bot), otherwise we already sent a new one
    if status_msg or isinstance(target, types.CallbackQuery):
         try:
             await msg.edit_text(f"🔄 Анализирую: <i>{text}</i>...", parse_mode="HTML")
         except Exception:
             # Fallback if edit fails (old message)
             msg = await target.answer(f"🔄 Анализирую: <i>{text}</i>...", parse_mode="HTML")

    try:
        # 1. Check Saved Dishes
        dish_match = None
        async for session in get_db():
            stmt = select(SavedDish).where(SavedDish.user_id == user_id).where(SavedDish.name.ilike(text))
            res = await session.execute(stmt)
            dish_match = res.scalars().first()
            if dish_match:
                break

        if dish_match:
            name = dish_match.name
            calories = dish_match.total_calories
            protein = dish_match.total_protein
            fat = dish_match.total_fat
            carbs = dish_match.total_carbs
            fiber = dish_match.total_fiber
            weight_grams = None
            weight_missing = False
            base_name = name
        else:
            result = await NormalizationService.analyze_food_intake(text)
            logger.info(f"🍌 Normalization Result for '{text}': {result}")

            name = result.get("name", text)
            calories = safe_float(result.get("calories"))
            protein = safe_float(result.get("protein"))
            fat = safe_float(result.get("fat"))
            carbs = safe_float(result.get("carbs"))
            fiber = safe_float(result.get("fiber"))

            # --- WATER INTERCEPTION ---
            # If the user literally just drank water (or mineral water, hot water)
            if name.lower() in ["вода", "минеральная вода", "кипяток", "water"]:
                weight_grams = weight_override if weight_override else result.get("weight_grams")

                # If we don't know the amount, we should ask
                if not weight_grams or result.get("weight_missing", True):
                    await state.update_data(
                        pending_water=True,
                        intent="log"
                    )
                    await state.set_state(UniversalInputStates.waiting_for_weight)

                    builder = InlineKeyboardBuilder()
                    builder.button(text="❌ Отмена", callback_data="u_action_cancel")

                    await msg.edit_text(
                        f"🧐 Вы сказали: {text}\n"
                        f"Это похоже на: <b>{name}</b>\n\n"
                        f"💧 <b>Сколько миллилитров?</b> (Напишите число)",
                        parse_mode="HTML",
                        reply_markup=builder.as_markup()
                    )
                    return

                # We have the amount, log it
                amount_ml = int(weight_grams)
                from database.models import WaterLog
                async for session in get_db():
                    log = WaterLog(
                        user_id=user_id,
                        amount_ml=amount_ml
                    )
                    session.add(log)
                    await session.commit()

                await target.answer(f"✅ Добавлено {amount_ml} мл воды!")

                # Show updated dashboard
                from handlers.menu import show_main_menu
                await show_main_menu(msg, target.from_user.first_name, user_id)
                return
            # --------------------------

            # Validate name quality
            invalid_names = ["не указано", "unknown", "продукт", "еда", "блюдо"]
            if name.lower() in invalid_names or len(name) < 2:
                # Save context to ask for name
                await state.update_data(
                    pending_clarification={
                        "weight_override": weight_override if weight_override else result.get("weight_grams"),
                        "intent": "log"
                    }
                )
                await state.set_state(UniversalInputStates.waiting_for_product_name)

                await msg.edit_text(
                    f"🤔 <b>Я понял вес ({weight_override if weight_override else '?' }г), но не понял, что это за продукт.</b>\n\n"
                    "Пожалуйста, скажите или напишите название (или пришлите фото упаковки).",
                    parse_mode="HTML"
                )
                return

            weight_grams = weight_override if weight_override else result.get("weight_grams")
            weight_missing = result.get("weight_missing", True) if not weight_override else False
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
                        "fiber100": fiber
                    },
                    intent="log"
                )
                await state.set_state(UniversalInputStates.waiting_for_weight)

                builder = InlineKeyboardBuilder()
                builder.button(text="🔢 В штуках", callback_data="u_mode_qty")
                builder.button(text="❌ Отмена", callback_data="u_action_cancel")
                builder.adjust(1, 1)

                await msg.edit_text(
                    f"🧐 Вы сказали: <i>{text}</i>\n"
                    f"Это похоже на: <b>{name}</b>\n\n"
                    f"⚖️ <b>Сколько грамм?</b> (Напишите число)",
                    parse_mode="HTML",
                    reply_markup=builder.as_markup()
                )
                return

            # Recalculate if override
            if weight_override:
                factor = weight_override / 100.0
                calories = calories * factor
                protein = protein * factor
                fat = fat * factor
                carbs = carbs * factor
                fiber = fiber * factor

        final_name = f"{name} ({weight_grams}г)" if weight_grams else name

        # Prepare data for confirmation
        # Ensure pending_product matches what i_ate expects
        await state.update_data(
            pending_product={
                "name": final_name,
                "base_name": base_name,
                "calories100": calories,
                "protein100": protein,
                "fat100": fat,
                "carbs100": carbs,
                "fiber100": fiber
            }
        )

        # Redirect to I Ate Confirmation
        await show_confirmation_interface(msg, state)
        # Note: We do NOT clear state here, show_confirmation_interface sets its own state

    except Exception as e:
        logger.error(f"Text Log Error: {e}", exc_info=True)
        await msg.edit_text(f"❌ Ошибка: {e}")
        await state.clear()


async def process_photo_food_logging(
    target: types.CallbackQuery | types.Message,
    state: FSMContext,
    file_id: str
):
    """Log food from photo."""
    if isinstance(target, types.CallbackQuery):
        msg = target.message
        bot = target.bot
    else:
        msg = target
        bot = msg.bot # accessible from message

    try:
        await msg.edit_text("⏳ Анализирую фото блюда...")
    except Exception:
        msg = await msg.answer("⏳ Анализирую фото блюда...")

    try:
        import io

        from services.ai import AIService

        file_info = await bot.get_file(file_id)
        photo_bytes = io.BytesIO()
        await bot.download_file(file_info.file_path, photo_bytes)

        product_data = await AIService.recognize_product_from_image(photo_bytes.getvalue())

        if not product_data or not product_data.get("name"):
            product_data = {"name": "Неизвестное блюдо", "calories": 200, "protein": 10, "fat": 10, "carbs": 20, "fiber": 0}

        # Reuse pending structure but stay in our state?
        # Or switch to Waiting for Weight

        await state.update_data(
            pending_product={
                "name": product_data["name"],
                "base_name": product_data["name"],
                "calories100": float(product_data.get("calories", 0)), # Vision usually gives per 100g estimate? Or total?
                # Currently AIService.recognize usually gives estimate for the dish.
                # Let's assume it returns per 100g for consistency or total?
                # Actually AIService.recognize prompt asks for "average KBZHU per 100g".
                "protein100": float(product_data.get("protein", 0)),
                "fat100": float(product_data.get("fat", 0)),
                "carbs100": float(product_data.get("carbs", 0)),
                "fiber100": float(product_data.get("fiber", 0))
            }
        )

        await state.set_state(UniversalInputStates.waiting_for_weight)

        builder = InlineKeyboardBuilder()
        builder.button(text="❌ Отмена", callback_data="u_action_cancel")

        await msg.edit_text(
            f"🍽️ <b>{product_data['name']}</b>\n\n"
            f"⚖️ <b>Введите вес в граммах</b> (например: 150)",
            parse_mode="HTML", reply_markup=builder.as_markup()
        )

    except Exception as e:
        logger.error(f"Photo Log Error: {e}", exc_info=True)
        await msg.edit_text(f"❌ Ошибка: {e}")


async def process_text_fridge_add(
    target: types.CallbackQuery | types.Message,
    state: FSMContext,
    text: str,
    weight_override: float | None = None,
    status_msg: types.Message | None = None
):
    """Add text product to fridge."""
    user_id = target.from_user.id

    # Determine message to update/reply
    if status_msg:
        msg = status_msg
    elif isinstance(target, types.CallbackQuery):
        msg = target.message
    else:
        # target is user message, so we must reply
        msg = await target.answer(f"🔄 Добавляю в холодильник: <i>{text}</i>...", parse_mode="HTML")

    # Try to edit if it's our message (bot)
    if status_msg or isinstance(target, types.CallbackQuery):
        try:
            await msg.edit_text(f"🔄 Добавляю в холодильник: <i>{text}</i>...", parse_mode="HTML")
        except Exception:
            msg = await target.answer(f"🔄 Добавляю в холодильник: <i>{text}</i>...", parse_mode="HTML")

    try:
        result = await NormalizationService.analyze_food_intake(text)

        name = result.get("name", text)
        calories = safe_float(result.get("calories"))
        protein = safe_float(result.get("protein"))
        fat = safe_float(result.get("fat"))
        carbs = safe_float(result.get("carbs"))
        fiber = safe_float(result.get("fiber"))
        weight_grams = weight_override if weight_override else result.get("weight_grams")

        weight_missing = result.get("weight_missing", True) if not weight_override else False
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
                    "fiber100": fiber
                },
                intent="fridge"
            )
            await state.set_state(UniversalInputStates.waiting_for_weight)

            builder = InlineKeyboardBuilder()
            builder.button(text="🔢 В штуках", callback_data="u_mode_qty")
            builder.button(text="❌ Отмена", callback_data="u_action_cancel")
            builder.adjust(1, 1)

            await msg.edit_text(
                f"🧊 <b>В холодильник:</b>\n"
                f"📦 {name}\n\n"
                f"⚖️ <b>Сколько грамм?</b> (Напишите число)",
                parse_mode="HTML",
                reply_markup=builder.as_markup()
            )
            return

        # Recalculate if override
        if weight_override:
            factor = weight_override / 100.0
            calories = calories * factor
            protein = protein * factor
            fat = fat * factor
            carbs = carbs * factor
            fiber = fiber * factor

        async for session in get_db():
            product = Product(
                user_id=user_id,
                name=name,
                category="Manual",
                calories=calories,
                protein=protein,
                fat=fat,
                carbs=carbs,
                fiber=fiber,
                price=0.0,
                quantity=1.0,
                weight_g=float(weight_grams),
                source="universal_text"
            )
            session.add(product)
            await session.commit()
            product_id = product.id

        await state.clear()

        builder = InlineKeyboardBuilder()
        builder.button(text="🍽️ Нет, я это съел(а)", callback_data=f"u_move_to_ate:{product_id}")

        await msg.edit_text(
            f"✅ <b>Добавлено в холодильник!</b>\n"
            f"📦 {name} ({weight_grams}г)\n"
            f"🔥 <b>{int(calories)}</b> ккал\n"
            f"🥩 {protein:.1f} | 🥑 {fat:.1f} | 🍞 {carbs:.1f} | 🥬 {fiber:.1f}",
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )

    except Exception as e:
        logger.error(f"Fridge Add Error: {e}")
        await msg.edit_text(f"❌ Ошибка: {e}")


async def process_photo_fridge_add(
    target: types.CallbackQuery | types.Message,
    state: FSMContext,
    file_id: str
):
    """Add photo product to fridge."""
    if isinstance(target, types.CallbackQuery):
        msg = target.message
        bot = target.bot
    else:
        msg = target
        bot = msg.bot

    try:
        await msg.edit_text("⏳ Анализирую фото...")
    except Exception:
        msg = await msg.answer("⏳ Анализирую фото...")

    try:
        import io

        from services.ai import AIService

        file_info = await bot.get_file(file_id)
        photo_bytes = io.BytesIO()
        await bot.download_file(file_info.file_path, photo_bytes)

        product_data = await AIService.recognize_product_from_image(photo_bytes.getvalue())

        if not product_data:
             await msg.edit_text("❌ Не распознано.")
             return

        # Ask for weight just like text
        await state.update_data(
            pending_product={
                "name": product_data.get("name", "Продукт"),
                "base_name": product_data.get("name", "Продукт"),
                "calories100": float(product_data.get("calories", 0)),
                "protein100": float(product_data.get("protein", 0)),
                "fat100": float(product_data.get("fat", 0)),
                "carbs100": float(product_data.get("carbs", 0)),
                "fiber100": float(product_data.get("fiber", 0))
            },
            intent="fridge"
        )

        await state.set_state(UniversalInputStates.waiting_for_weight)

        builder = InlineKeyboardBuilder()
        builder.button(text="❌ Отмена", callback_data="u_action_cancel")

        await msg.edit_text(
             f"🧊 <b>В холодильник:</b>\n"
             f"📦 {product_data.get('name')}\n\n"
             f"⚖️ <b>Сколько грамм?</b> (Напишите число)",
             parse_mode="HTML",
             reply_markup=builder.as_markup()
        )

    except Exception as e:
        logger.error(f"Photo Fridge Error: {e}", exc_info=True)
        await msg.edit_text(f"Ошибка: {e}")


async def process_herbalife_input(
    target: types.CallbackQuery | types.Message,
    state: FSMContext,
    text: str,
    status_msg: types.Message | None = None
):
    """Specialized handler for Herbalife products."""
    user_id = target.from_user.id

    if status_msg:
        msg = status_msg
    elif isinstance(target, types.CallbackQuery):
        msg = target.message
    else:
        msg = await target.answer("🌿 Обрабатываю Гербалайф...")

    try:
        if isinstance(msg, types.Message) and msg.from_user.is_bot:
            try:
                await msg.edit_text("🌿 <b>Эксперт Гербалайф:</b> Анализирую...", parse_mode="HTML")
            except Exception:
                pass

        # 1. Resolve Product
        product = await herbalife_expert.find_product_by_alias(text)
        if not product:
            await msg.edit_text(
                "❌ <b>Продукт не найден в базе Гербалайф.</b>\n"
                "Попробуйте уточнить название (например: Ф1, ОЯН, Белок)."
            )
            return

        # 2. Parse Quantity
        qty_data = herbalife_expert.parse_quantity(text)

        # 3. Calculate
        nutr = herbalife_expert.calculate_nutrition(product, qty_data["amount"], qty_data["unit"])

        # 4. Save to Log
        final_name = f"{nutr['name']} ({int(nutr['weight'])}г/ед)"
        async for session in get_db():
            from database.models import ConsumptionLog
            log = ConsumptionLog(
                user_id=user_id,
                product_name=final_name,
                base_name=product["id"],
                calories=nutr["calories"],
                protein=nutr["protein"],
                fat=nutr["fat"],
                carbs=nutr["carbs"],
                fiber=nutr["fiber"],
                date=datetime.now()
            )
            session.add(log)
            await session.commit()

        await state.clear()

        # 5. Success UI
        warnings_text = ""
        if nutr["warnings"]:
            warnings_text = "\n\n⚠️ <b>Важно:</b>\n" + "\n".join([f"• {w}" for w in nutr["warnings"]])

        await msg.edit_text(
            f"🌿 <b>Записано по базе эксперта!</b>\n\n"
            f"🍽️ {final_name}\n\n"
            f"🔥 <b>{int(nutr['calories'])}</b> ккал\n"
            f"🥩 {nutr['protein']:.1f} | 🥑 {nutr['fat']:.1f} | 🍞 {nutr['carbs']:.1f} | 🥬 {nutr['fiber']:.1f}"
            f"{warnings_text}",
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Herbalife Expert Error: {e}", exc_info=True)
        await msg.edit_text(f"❌ Ошибка эксперта: {e}")


@router.message(UniversalInputStates.waiting_for_weight, F.text)
async def handle_universal_weight(message: types.Message, state: FSMContext) -> None:
    """Handle weight input for pending product."""
    try:
        weight_text = message.text.replace(',', '.').strip()
        import re
        match = re.search(r'(\d+(?:\.\d+)?)', weight_text)

        if not match:
            await message.reply("⚠️ Пожалуйста, введите только число (вес в граммах).")
            return

        weight = float(match.group(1))

        data = await state.get_data()
        product = data.get("pending_product")
        intent = data.get("intent", "log") # 'log' or 'fridge'

        # Recalculate based on weight
        factor = weight / 100.0

        name = product['name']
        base_name = product['base_name']
        calories = product['calories100'] * factor
        protein = product['protein100'] * factor
        fat = product['fat100'] * factor
        carbs = product['carbs100'] * factor
        fiber = product['fiber100'] * factor

        final_name = f"{name} ({int(weight)}г)"

        async for session in get_db():
            if intent == "fridge":
                # Save to Fridge (Product)
                prod = Product(
                    user_id=message.from_user.id,
                    name=name, # Keep original name, weight is separate
                    category="Manual",
                    calories=calories,
                    protein=protein,
                    fat=fat,
                    carbs=carbs,
                    fiber=fiber,
                    price=0.0,
                    quantity=1.0,
                    weight_g=weight,
                    source="universal_input"
                )
                session.add(prod)
                await session.commit()
                product_id = prod.id

                await state.clear()

                builder = InlineKeyboardBuilder()
                builder.button(text="🍽️ Нет, я это съел(а)", callback_data=f"u_move_to_ate:{product_id}")

                success_text = (
                    f"✅ <b>Добавлено в холодильник!</b>\n\n"
                    f"📦 {final_name}\n"
                    f"🔥 <b>{int(calories)}</b> ккал\n"
                    f"🥩 {protein:.1f} | 🥑 {fat:.1f} | 🍞 У: {carbs:.1f} | 🥬 Кл: {fiber:.1f}"
                )
                await message.reply(success_text, parse_mode="HTML", reply_markup=builder.as_markup())
            else:
                # Redirect to I Ate Confirmation
                await state.update_data(
                    pending_product={
                        "name": final_name,
                        "base_name": base_name,
                        "calories100": calories,
                        "protein100": protein,
                        "fat100": fat,
                        "carbs100": carbs,
                        "fiber100": fiber
                    }
                )
                await show_confirmation_interface(message, state)

    except Exception as e:
        logger.error(f"Univ Weight Error: {e}", exc_info=True)
        await message.reply(f"❌ Ошибка: {e}")
        await state.clear()


@router.message(UniversalInputStates.waiting_for_weight, F.voice)
async def handle_weight_voice(message: types.Message, bot: Bot, state: FSMContext) -> None:
    """Handle weight input via voice."""
    status_msg = await message.reply("🎤 Слушаю вес...")

    try:
        file_info = await bot.get_file(message.voice.file_id)
        temp_dir = "services/temp"
        os.makedirs(temp_dir, exist_ok=True)
        ogg_path = f"{temp_dir}/weight_{message.voice.file_id}.ogg"
        await bot.download_file(file_info.file_path, ogg_path)

        text = await stt_engine.process_voice_message(ogg_path)
        try:
            os.remove(ogg_path)
        except Exception:
            pass

        if not text:
            await status_msg.edit_text("❌ Не удалось распознать. Напишите числом.")
            return

        # Extract number from text
        import re
        match = re.search(r'(\d+(?:\.\d+)?)', text.replace(',', '.'))
        if match:
            # Inject simulated text message to reuse logic
            message.text = match.group(1)
            await status_msg.delete()
            await handle_universal_weight(message, state)
        else:
            await status_msg.edit_text(f"🤔 Вы сказали \"{text}\", но я не услышал число. Напишите вес.")

    except Exception as e:
        logger.error(f"Weight Voice Error: {e}")
        await status_msg.edit_text("❌ Ошибка обработки голоса.")


# --- CLARIFICATION PAIRS ---

@router.message(UniversalInputStates.waiting_for_product_name, F.text)
async def handle_clarification_text(message: types.Message, state: FSMContext) -> None:
    """Handle product name clarification via text."""
    data = await state.get_data()
    pending = data.get("pending_clarification", {})
    weight_val = pending.get("weight_override") # might be None
    intent = pending.get("intent", "log")

    new_name = message.text.strip()

    # Rerun processing with new name and OLD weight
    if intent == "log":
        await process_text_food_logging(message, state, new_name, weight_override=weight_val)
    elif intent == "fridge":
        await process_text_fridge_add(message, state, new_name, weight_override=weight_val)


@router.message(UniversalInputStates.waiting_for_product_name, F.voice)
async def handle_clarification_voice(message: types.Message, bot: Bot, state: FSMContext) -> None:
    """Handle product name clarification via voice."""
    status_msg = await message.reply("🎤 Слушаю уточнение...")

    try:
        file_info = await bot.get_file(message.voice.file_id)
        temp_dir = "services/temp"
        os.makedirs(temp_dir, exist_ok=True)
        ogg_path = f"{temp_dir}/clarify_{message.voice.file_id}.ogg"
        await bot.download_file(file_info.file_path, ogg_path)

        text = await stt_engine.process_voice_message(ogg_path)
        try:
            os.remove(ogg_path)
        except Exception:
            pass

        if not text:
            await status_msg.edit_text("❌ Не удалось распознать. Напишите текстом.")
            return

        data = await state.get_data()
        pending = data.get("pending_clarification", {})
        weight_val = pending.get("weight_override")
        intent = pending.get("intent", "log")

        if intent == "log":
            await process_text_food_logging(message, state, text, weight_override=weight_val, status_msg=status_msg)
        elif intent == "fridge":
            await process_text_fridge_add(message, state, text, weight_override=weight_val, status_msg=status_msg)

    except Exception as e:
        logger.error(f"Clarification Voice Error: {e}")
        await status_msg.edit_text("❌ Ошибка обработки голоса.")


@router.message(UniversalInputStates.waiting_for_product_name, F.photo)
async def handle_clarification_photo(message: types.Message, bot: Bot, state: FSMContext) -> None:
    """Handle product name clarification via photo."""
    status_msg = await message.reply("📸 Смотрю что это...")

    try:
        import io

        from services.ai import AIService

        file_info = await bot.get_file(message.photo[-1].file_id)
        photo_bytes = io.BytesIO()
        await bot.download_file(file_info.file_path, photo_bytes)

        product_data = await AIService.recognize_product_from_image(photo_bytes.getvalue())
        name = product_data.get("name") if product_data else None

        if not name:
             await status_msg.edit_text("❌ Не удалось узнать продукт по фото. Напишите название.")
             return

        data = await state.get_data()
        pending = data.get("pending_clarification", {})
        weight_val = pending.get("weight_override")
        intent = pending.get("intent", "log")

        if intent == "log":
            await process_text_food_logging(status_msg, state, name, weight_override=weight_val)
        elif intent == "fridge":
            await process_text_fridge_add(status_msg, state, name, weight_override=weight_val)

    except Exception as e:
        logger.error(f"Clarification Photo Error: {e}")
        await status_msg.edit_text("❌ Ошибка обработки фото.")


# --- BATCH (MULTI-ITEM) FOOD LOGGING ---

async def process_batch_food_logging(
    message: types.Message,
    state: FSMContext,
    items: list[dict],
    status_msg: types.Message | None = None
) -> None:
    """Process multiple food items at once. Entry point for batch flow."""

    # Show loading
    if status_msg:
        await status_msg.edit_text(
            f"🧠 <b>Анализирую {len(items)} продуктов...</b>",
            parse_mode="HTML"
        )
    else:
        status_msg = await message.reply(
            f"🧠 <b>Анализирую {len(items)} продуктов...</b>",
            parse_mode="HTML"
        )

    try:
        # Get KBJU for all items in one AI call
        results = await NormalizationService.analyze_food_intake_batch(items)

        # Prepare batch_items for state
        batch_items = []
        for i, res in enumerate(results):
            batch_items.append({
                "name": res.get("name", items[i]["product"] if i < len(items) else "?"),
                "base_name": res.get("base_name", res.get("name", "")),
                "calories": safe_float(res.get("calories")),
                "protein": safe_float(res.get("protein")),
                "fat": safe_float(res.get("fat")),
                "carbs": safe_float(res.get("carbs")),
                "fiber": safe_float(res.get("fiber")),
                "weight_grams": res.get("weight_grams"),
                "selected": True  # All selected by default
            })

        await state.update_data(batch_items=batch_items, batch_edit_index=0)
        await state.set_state(UniversalInputStates.batch_confirmation)

        # Render the batch list
        text, markup = _render_batch_list(batch_items)
        await status_msg.edit_text(text, parse_mode="HTML", reply_markup=markup)

    except Exception as e:
        logger.error(f"Batch processing error: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Ошибка пакетной обработки: {e}")
        await state.clear()


def _render_batch_list(batch_items: list[dict]) -> tuple[str, types.InlineKeyboardMarkup]:
    """Render the batch confirmation list UI."""
    lines = []
    total_cal = 0
    total_p = 0
    total_f = 0
    total_c = 0
    total_fi = 0
    selected_count = 0

    for i, item in enumerate(batch_items, 1):
        check = "✅" if item["selected"] else "⬜"
        cal = int(item["calories"])
        total_cal += cal if item["selected"] else 0
        total_p += item["protein"] if item["selected"] else 0
        total_f += item["fat"] if item["selected"] else 0
        total_c += item["carbs"] if item["selected"] else 0
        total_fi += item.get("fiber", 0) if item["selected"] else 0
        if item["selected"]:
            selected_count += 1
        lines.append(f"{check} {i}. {item['name']} — <b>{cal}</b> ккал")

    items_text = "\n".join(lines)

    text = (
        f"📋 <b>Введено {len(batch_items)} продуктов:</b>\n\n"
        f"{items_text}\n\n"
        f"{'─' * 20}\n"
        f"🔥 <b>Итого ({selected_count} шт):</b> {int(total_cal)} ккал\n"
        f"🥩 Б: {total_p:.1f} | 🥑 Ж: {total_f:.1f} | 🍞 У: {total_c:.1f} | 🥬 Кл: {total_fi:.1f}"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text=f"✅ Прямо сейчас ({selected_count})", callback_data="batch_confirm_now")
    builder.button(text="🕓 Другое время", callback_data="batch_ask_time")
    builder.button(text="✏️ Редактировать", callback_data="batch_edit_start")
    builder.button(text="🥗 Это одно блюдо", callback_data="u_combine_to_single")
    builder.button(text="❌ Отмена", callback_data="batch_cancel")
    builder.adjust(2, 2, 1, 1)

    return text, builder.as_markup()


def _render_batch_edit_item(batch_items: list[dict], index: int) -> tuple[str, types.InlineKeyboardMarkup]:
    """Render edit view for a single batch item."""
    item = batch_items[index]
    total = len(batch_items)
    check = "✅" if item["selected"] else "⬜"

    text = (
        f"✏️ <b>Продукт {index + 1}/{total}:</b>\n\n"
        f"{check} <b>{item['name']}</b>\n\n"
        f"🔥 Ккал: <b>{int(item['calories'])}</b>\n"
        f"🥩 Б: <b>{item['protein']:.1f}</b> | "
        f"🥑 Ж: <b>{item['fat']:.1f}</b> | "
        f"🍞 У: <b>{item['carbs']:.1f}</b>"
    )

    builder = InlineKeyboardBuilder()

    # Navigation
    nav_buttons = []
    if index > 0:
        nav_buttons.append(types.InlineKeyboardButton(text="⬅️ Пред.", callback_data=f"batch_nav:{index - 1}"))
    if index < total - 1:
        nav_buttons.append(types.InlineKeyboardButton(text="➡️ След.", callback_data=f"batch_nav:{index + 1}"))
    if nav_buttons:
        builder.row(*nav_buttons)

    # Toggle selection / Delete
    if item["selected"]:
        builder.button(text="⬜ Убрать из записи", callback_data=f"batch_toggle:{index}")
    else:
        builder.button(text="✅ Вернуть в запись", callback_data=f"batch_toggle:{index}")

    builder.button(text="🗑️ Удалить совсем", callback_data=f"batch_delete:{index}")
    builder.button(text="✏️ Редактировать КБЖУ", callback_data=f"batch_item_macros:{index}")
    builder.adjust(2 if nav_buttons else 1, 1, 1, 1)

    # Back to list
    builder.button(text="🔙 К списку", callback_data="batch_back_to_list")

    return text, builder.as_markup()


def _render_batch_item_macros_menu(batch_items: list[dict], index: int) -> tuple[str, types.InlineKeyboardMarkup]:
    """Render the macros selection menu for a single batch item."""
    item = batch_items[index]

    text = (
        f"<b>✏️ Редактирование: {item['name']}</b>\n\n"
        f"🔥 Ккал: <code>{int(item['calories'])}</code>\n"
        f"🥩 Б: <code>{item['protein']:.1f}</code> | 🥑 Ж: <code>{item['fat']:.1f}</code> | 🍞 У: <code>{item['carbs']:.1f}</code>\n"
        f"🥬 Кл: <code>{item.get('fiber', 0):.1f}</code>\n\n"
        f"Выберите поле для изменения:"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="🔥 Ккал", callback_data=f"batch_item_edit_field:calories:{index}")
    builder.button(text="🥩 Бел.", callback_data=f"batch_item_edit_field:protein:{index}")
    builder.button(text="🥑 Жир.", callback_data=f"batch_item_edit_field:fat:{index}")
    builder.button(text="🍞 Угл.", callback_data=f"batch_item_edit_field:carbs:{index}")
    builder.button(text="🥬 Кл.", callback_data=f"batch_item_edit_field:fiber:{index}")
    builder.button(text="🔙 Назад", callback_data=f"batch_back_to_item:{index}")
    builder.adjust(2, 3, 1)

    return text, builder.as_markup()


# --- BATCH CALLBACKS ---

@router.callback_query(F.data == "batch_confirm_now", StateFilter(UniversalInputStates.batch_confirmation, UniversalInputStates.batch_editing))
async def batch_confirm_now(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Save all items with current time."""
    await batch_confirm_all(callback, state, datetime.now())

@router.callback_query(F.data == "batch_ask_time", StateFilter(UniversalInputStates.batch_confirmation, UniversalInputStates.batch_editing))
async def batch_ask_time(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Show time picker for the whole batch."""
    from utils.time_picker import get_time_picker_keyboard
    await state.set_state(UniversalInputStates.batch_time_selection)
    await callback.message.edit_text(
        "🕓 <b>Когда вы это съели?</b>\n\nВыбранное время применится ко всем продуктам в списке:",
        parse_mode="HTML",
        reply_markup=get_time_picker_keyboard("batch_time")
    )

@router.callback_query(F.data.startswith("batch_time:"), UniversalInputStates.batch_time_selection)
async def process_batch_time_selection(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Handle time selection for batch."""
    if callback.data == "batch_time:back":
        # This is a placeholder for a potential back button in time picker,
        # but the current time picker doesn't have a "back" to batch summary.
        # If it did, we'd need a _render_batch_summary function.
        # For now, let's assume it goes back to the main batch confirmation view.
        data = await state.get_data()
        batch_items = data.get("batch_items", [])
        text, markup = _render_batch_list(batch_items) # Use _render_batch_list for summary
        await callback.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
        await state.set_state(UniversalInputStates.batch_confirmation)
        return

    from utils.time_picker import get_time_from_callback
    selected_time = get_time_from_callback(callback.data)
    await batch_confirm_all(callback, state, selected_time)

async def batch_confirm_all(callback: types.CallbackQuery, state: FSMContext, timestamp: datetime) -> None:
    """Save all selected batch items to DB with specified timestamp."""
    data = await state.get_data()
    batch_items = data.get("batch_items", [])
    selected = [item for item in batch_items if item.get("selected", True)]

    if not selected:
        await callback.answer("⚠️ Нет выбранных продуктов!", show_alert=True)
        return

    user_id = callback.from_user.id
    saved_count = 0
    total_cal = 0

    async for session in get_db():
        for item in selected:
            log = ConsumptionLog(
                user_id=user_id,
                product_name=item["name"],
                base_name=item.get("base_name"),
                calories=item.get("calories", 0),
                protein=item.get("protein", 0),
                fat=item.get("fat", 0),
                carbs=item.get("carbs", 0),
                fiber=item.get("fiber", 0),
                date=timestamp
            )
            session.add(log)
            saved_count += 1
            total_cal += int(item.get("calories", 0))
        await session.commit()

    await state.clear()

    # Build success message
    time_str = timestamp.strftime("%H:%M")
    await callback.message.edit_text(
        f"✅ <b>Записано {saved_count} продуктов!</b> ({time_str})\n"
        f"🔥 Общая калорийность: <b>{total_cal}</b> ккал",
        parse_mode="HTML"
    )

    # NEW: Send visual progress card
    from services.reports import send_daily_visual_report
    await send_daily_visual_report(callback.from_user.id, callback.bot)

    await callback.answer()


@router.callback_query(F.data == "batch_cancel", UniversalInputStates.batch_confirmation)
async def batch_cancel(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Cancel batch input."""
    await state.clear()
    await callback.message.edit_text("❌ Ввод отменен.")
    await callback.answer()


@router.callback_query(F.data == "batch_edit_start", UniversalInputStates.batch_confirmation)
async def batch_edit_start(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Enter edit mode for batch items."""
    data = await state.get_data()
    batch_items = data.get("batch_items", [])

    if not batch_items:
        await callback.answer("⚠️ Список пуст!")
        return

    await state.set_state(UniversalInputStates.batch_editing)
    await state.update_data(batch_edit_index=0)

    text, markup = _render_batch_edit_item(batch_items, 0)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data.startswith("batch_nav:"), UniversalInputStates.batch_editing)
async def batch_nav(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Navigate between batch items in edit mode."""
    index = int(callback.data.split(":")[1])
    data = await state.get_data()
    batch_items = data.get("batch_items", [])

    if 0 <= index < len(batch_items):
        await state.update_data(batch_edit_index=index)
        text, markup = _render_batch_edit_item(batch_items, index)
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data.startswith("batch_item_macros:"), UniversalInputStates.batch_editing)
async def batch_item_macros(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Show macros edit menu for a specific item."""
    index = int(callback.data.split(":")[1])
    data = await state.get_data()
    batch_items = data.get("batch_items", [])
    if not batch_items:
        await callback.answer("Ошибка данных", show_alert=True)
        return

    text, markup = _render_batch_item_macros_menu(batch_items, index)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data.startswith("batch_item_edit_field:"), UniversalInputStates.batch_editing)
async def batch_item_edit_field(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Ask for a macro value for a specific item."""
    parts = callback.data.split(":")
    field = parts[1]
    index = int(parts[2])

    await state.update_data(current_batch_edit_field=field, current_batch_edit_index=index)
    await state.set_state(UniversalInputStates.batch_waiting_for_macro_value)

    labels = {
        "calories": "Калории", "protein": "Белки",
        "fat": "Жиры", "carbs": "Углеводы", "fiber": "Клетчатку"
    }

    await callback.message.edit_text(f"✏️ Введите новое значение для <b>{labels.get(field)}</b>:", parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("batch_back_to_item:"), UniversalInputStates.batch_editing)
async def batch_back_to_item(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Back from macros menu to item info."""
    index = int(callback.data.split(":")[1])
    data = await state.get_data()
    batch_items = data.get("batch_items", [])
    if not batch_items:
        await callback.answer("Ошибка данных", show_alert=True)
        return

    text, markup = _render_batch_edit_item(batch_items, index)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
    await callback.answer()


@router.message(UniversalInputStates.batch_waiting_for_macro_value)
async def batch_save_macro_value(message: types.Message, state: FSMContext) -> None:
    """Save the new macro value and return to item view."""
    try:
        value = float(message.text.replace(',', '.').replace('г', '').strip())
        data = await state.get_data()
        field = data.get("current_batch_edit_field")
        index = data.get("current_batch_edit_index")
        batch_items = data.get("batch_items", [])

        if field and index is not None and index < len(batch_items):
            batch_items[index][field] = value
            await state.update_data(batch_items=batch_items)

            # Go back to item edit view
            await state.set_state(UniversalInputStates.batch_editing)
            text, markup = _render_batch_edit_item(batch_items, index)
            await message.answer(text, parse_mode="HTML", reply_markup=markup)
        else:
            await message.answer("⚠️ Ошибка контекста. Попробуйте еще раз.")
            await state.set_state(UniversalInputStates.batch_editing)

    except ValueError:
        await message.answer("⚠️ Пожалуйста, введите корректное число.")


@router.callback_query(F.data.startswith("batch_toggle:"), UniversalInputStates.batch_editing)
async def batch_toggle(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Toggle item selection (include/exclude from save)."""
    index = int(callback.data.split(":")[1])
    data = await state.get_data()
    batch_items = data.get("batch_items", [])

    if 0 <= index < len(batch_items):
        batch_items[index]["selected"] = not batch_items[index]["selected"]
        await state.update_data(batch_items=batch_items)

        text, markup = _render_batch_edit_item(batch_items, index)
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data.startswith("batch_delete:"), UniversalInputStates.batch_editing)
async def batch_delete(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Delete item from batch entirely."""
    index = int(callback.data.split(":")[1])
    data = await state.get_data()
    batch_items = data.get("batch_items", [])

    if 0 <= index < len(batch_items):
        deleted_name = batch_items[index]["name"]
        batch_items.pop(index)
        await state.update_data(batch_items=batch_items)

        if not batch_items:
            await state.clear()
            await callback.message.edit_text("🗑️ Все продукты удалены. Ввод отменен.")
            await callback.answer()
            return

        # Adjust index if needed
        new_index = min(index, len(batch_items) - 1)
        await state.update_data(batch_edit_index=new_index)

        text, markup = _render_batch_edit_item(batch_items, new_index)
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
        await callback.answer(f"🗑️ Удалено: {deleted_name}")
    else:
        await callback.answer()


@router.callback_query(F.data == "batch_back_to_list", UniversalInputStates.batch_editing)
async def batch_back_to_list(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Return from edit mode to batch list."""
    data = await state.get_data()
    batch_items = data.get("batch_items", [])

    await state.set_state(UniversalInputStates.batch_confirmation)

    text, markup = _render_batch_list(batch_items)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
    await callback.answer()


# Also handle batch_confirm_all from editing state
@router.callback_query(F.data == "batch_confirm_now", UniversalInputStates.batch_editing)
async def batch_confirm_now_from_edit(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Save all from edit state now."""
    await batch_confirm_now(callback, state)

@router.callback_query(F.data == "batch_confirm_all", UniversalInputStates.batch_editing)
async def batch_confirm_all_from_edit(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Redirect to main confirm handler."""
    # This handler is for "confirm all" from the editing state.
    # It should transition back to the confirmation state and then trigger the time selection flow.
    await state.set_state(UniversalInputStates.batch_confirmation)
    await batch_ask_time(callback, state)


# --- SPLIT / COMBINE HANDLERS ---

@router.callback_query(F.data == "u_split_to_batch")
async def handle_split_to_batch(callback: types.CallbackQuery, state: FSMContext) -> None:
    """User wants to split a single product into multiple items."""
    data = await state.get_data()
    # Try to find description in different possible places
    description = (data.get("pending_product", {}).get("original_text") or
                   data.get("universal_data", {}).get("content") or
                   callback.message.text)

    if not description:
        # Fallback for i_ate context
        if "🍽️" in callback.message.text:
             description = callback.message.text.split("\n")[2].strip().strip("🍽️ ")

    if not description:
        await callback.answer("❌ Ошибка: не удалось найти исходный текст.", show_alert=True)
        return

    status_msg = await callback.message.answer("🔄 <b>Разделяю на ингредиенты...</b>", parse_mode="HTML")
    await callback.answer()

    try:
        # Call AI Brain with force_multi=True
        brain_result = await AIBrainService.analyze_text(description, force_multi=True)

        if brain_result and isinstance(brain_result, dict) and brain_result.get("multi") and brain_result.get("items"):
            items = brain_result["items"]
            from handlers.universal_input import process_batch_food_logging
            await process_batch_food_logging(callback.message, state, items, status_msg)
            # Remove the message with "Single" mode
            try:
                await callback.message.delete()
            except Exception:
                pass
        else:
            await status_msg.edit_text("❌ ИИ не смог разделить этот ввод на отдельные продукты.")
    except Exception as e:
        logger.error(f"Split Error: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Ошибка разделения: {e}")


@router.callback_query(F.data == "u_combine_to_single")
async def handle_combine_to_single(callback: types.CallbackQuery, state: FSMContext) -> None:
    """User wants to combine multiple items into one single dish."""
    data = await state.get_data()
    # Recover original description from universal_data if possible
    description = (data.get("universal_data", {}).get("content") or
                   callback.message.text.split("\n")[0].replace("📋 Введено", "").strip())

    if not description:
        await callback.answer("❌ Ошибка: не удалось найти основной текст.", show_alert=True)
        return

    status_msg = await callback.message.answer("🥗 <b>Объединяю в одно блюдо...</b>", parse_mode="HTML")
    await callback.answer()

    try:
        # Call AI Brain with force_single=True
        brain_result = await AIBrainService.analyze_text(description, force_single=True)

        if brain_result and isinstance(brain_result, dict) and not brain_result.get("multi"):
            product = brain_result.get("product")
            weight = brain_result.get("weight")

            # Route to single item flow
            from handlers.universal_input import process_text_food_logging
            await process_text_food_logging(callback.message, state, product, weight_override=weight, status_msg=status_msg)

            # Remove the message with "Batch" mode
            try:
                await callback.message.delete()
            except Exception:
                pass
        else:
            await status_msg.edit_text("❌ ИИ не смог объединить ввод в одно блюдо.")
    except Exception as e:
        logger.error(f"Combine Error: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Ошибка объединения: {e}")
