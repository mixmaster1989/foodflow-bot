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

from aiogram import Router, F, types, Bot
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import settings
from services.voice_stt import SpeechToText
from services.ai_brain import AIBrainService
from services.herbalife_expert import herbalife_expert
from services.normalization import NormalizationService
from database.models import ConsumptionLog, Product, SavedDish
from database.base import get_db
from sqlalchemy import select

router = Router()
logger = logging.getLogger(__name__)
stt_engine = SpeechToText()

class UniversalInputStates(StatesGroup):
    action_pending = State()      # Waiting for user to choose action
    waiting_for_weight = State()  # Waiting for weight input
    waiting_for_product_name = State() # Waiting for product name clarification
    waiting_for_intent = State()   # Waiting for intent clarification

# --- HANDLERS ---

@router.message(F.voice)
async def handle_voice(message: types.Message, bot: Bot, state: FSMContext) -> None:
    """Handle voice messages with STT."""
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
        except:
            pass
            
        if not text:
            await status_msg.edit_text("❌ Не удалось распознать речь.")
            return

        # Delegate to common processor
        await process_universal_input(message, "voice", text, state, status_msg)

    except Exception as e:
        logger.error(f"Voice Error: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Ошибка: {e}")


@router.message(F.photo, StateFilter(None))
async def handle_photo(message: types.Message, state: FSMContext) -> None:
    """Handle photos when no specific state is active. Auto-analyze content."""
    
    status_msg = await message.reply("👀 <b>Смотрю, что на фото...</b>", parse_mode="HTML")
    
    try:
        # 1. Analyze via Vision
        description = await AIBrainService.analyze_image(message, prompt="Что на фото? Если это еда или продукты, напиши название и вкус. Если чек - напиши 'чек'.")
        
        if not description:
             await status_msg.edit_text("❌ Не удалось понять, что на фото.")
             return

        # 2. Update status
        await status_msg.edit_text(f"👀 Вижу: <i>{description[:50]}...</i>", parse_mode="HTML")
        
        # 3. Process as text input
        # Combine caption if exists
        full_content = f"{description}"
        if message.caption:
            full_content = f"{message.caption} . На фото: {description}"
            
        await process_universal_input(message, "text", full_content, state, status_msg) # Treat as text now!
        
    except Exception as e:
        logger.error(f"Photo Analysis Error: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Ошибка анализа: {e}")


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
             await status_msg.edit_text(f"🧠 Думаю: <i>{content}</i>...", parse_mode="HTML")
        else:
             status_msg = await message.reply(f"🧠 Думаю: <i>{content}</i>...", parse_mode="HTML")
             
        brain_result = await AIBrainService.analyze_text(content)
        is_herbalife = await herbalife_expert.find_product_by_alias(content)
        
        # Safety check: brain_result must be a dict (AI sometimes returns list)
        if brain_result and isinstance(brain_result, dict) and brain_result.get("intent") in ["log_consumption", "add_to_fridge"] and not is_herbalife:
            intent = brain_result["intent"]
            product = brain_result.get("product") or content
            weight = brain_result.get("weight") # Float or null
            
            # Convert weight to float if string
            if weight:
                try:
                    weight = float(weight)
                except:
                    weight = None
            
            if intent == "log_consumption":
                # Pass message as TARGET (for user_id) and status_msg as STATUS (to edit)
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

    text_preview = f"📝 <i>\"{content}\"</i>" if content else ""
    header = "🤔 <b>Я не понял намерение.</b>\nСкажите: <i>\"Я съел\"</i> или <i>\"В холодильник\"</i>"
    
    if input_type == "voice":
        header = "🎤 <b>Голос распознан:</b>"
    elif input_type == "photo":
        header = "📸 <b>Фото получено:</b>"
    
    # Update header if it was just Unknown intent from Brain
    if input_type in ("text", "voice") and content:
         header = "🤔 <b>Я понял продукт, но не понял что сделать.</b>"

    msg_text = f"{header}\n\n{text_preview}\n\n👇 <b>Выберите действие или скажите голосом:</b>"

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
        try: os.remove(ogg_path)
        except: pass
        
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

@router.callback_query(UniversalInputStates.action_pending, F.data == "u_action_cancel")
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
    
    from services.photo_queue import PhotoQueueManager
    from handlers.receipt import process_receipt_worker_action
    
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
        from services.price_tag_ocr import PriceTagOCRService
        from database.models import PriceTag
        import io
        
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
         except:
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
            
            name = result.get("name", text)
            calories = float(result.get("calories") or 0)
            protein = float(result.get("protein") or 0)
            fat = float(result.get("fat") or 0)
            carbs = float(result.get("carbs") or 0)
            fiber = float(result.get("fiber") or 0)
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
                builder.button(text="❌ Отмена", callback_data="u_action_cancel")
                
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
        
        async for session in get_db():
            log = ConsumptionLog(
                user_id=user_id,
                product_name=final_name,
                base_name=base_name,
                calories=calories,
                protein=protein,
                fat=fat,
                carbs=carbs,
                fiber=fiber,
                date=datetime.utcnow()
            )
            session.add(log)
            await session.commit()
            
        await state.clear()
        
        weight_note = "" if weight_grams else "\n⚠️ <i>Вес не указан, посчитано на 100г.</i>"
        
        await msg.edit_text(
            f"✅ <b>Записано!</b>\n\n"
            f"🍽️ {final_name}\n\n"
            f"🔥 <b>{int(calories)}</b> ккал\n"
            f"🥩 {protein:.1f} | 🥑 {fat:.1f} | 🍞 {carbs:.1f}{weight_note}",
            parse_mode="HTML"
        )
        
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
    except:
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
        except:
            msg = await target.answer(f"🔄 Добавляю в холодильник: <i>{text}</i>...", parse_mode="HTML")
    
    try:
        result = await NormalizationService.analyze_food_intake(text)
        
        name = result.get("name", text)
        calories = float(result.get("calories") or 0)
        protein = float(result.get("protein") or 0)
        fat = float(result.get("fat") or 0)
        carbs = float(result.get("carbs") or 0)
        fiber = float(result.get("fiber") or 0)
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
            builder.button(text="❌ Отмена", callback_data="u_action_cancel")
            
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
            
        await state.clear()
        
        await msg.edit_text(
            f"✅ <b>Добавлено в холодильник!</b>\n"
            f"📦 {name} ({weight_grams}г)\n"
            f"🔥 <b>{int(calories)}</b> ккал\n"
            f"🥩 {protein:.1f} | 🥑 {fat:.1f} | 🍞 {carbs:.1f} | 🥬 {fiber:.1f}",
            parse_mode="HTML"
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
    except:
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
            except:
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
                date=datetime.utcnow()
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
                    calories=calories, # Total calories for this weight? Or per 100g?
                    # Product model usually stores nutrient PER 100g or PER ITEM?
                    # Let's check Product model. Usually it stores per unit or total?
                    # In process_text_fridge_add original: calories=calories (which was from analyze_food_intake, usually per 100g or total?)
                    # NormalizationService.analyze_food_intake returns total if weight provided, or per 100g if missing?
                    # Let's assume Product stores values FOR THE QUANTITY/WEIGHT.
                    # Wait, Product model usually has 'calories' field. Is it total or per 100g?
                    # Looking at i_ate: logs total calories.
                    # Looking at Product in receipt: stores total.
                    # So yes, we store TOTAL calories for the item.
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
                success_text = (
                    f"✅ <b>Добавлено в холодильник!</b>\n\n"
                    f"📦 {final_name}\n"
                    f"🔥 <b>{int(calories)}</b> ккал\n"
                    f"🥩 {protein:.1f} | 🥑 {fat:.1f} | 🍞 {carbs:.1f} | 🥬 {fiber:.1f}"
                )
            else:
                # Save to ConsumptionLog
                log = ConsumptionLog(
                    user_id=message.from_user.id,
                    product_name=final_name,
                    base_name=base_name,
                    calories=calories,
                    protein=protein,
                    fat=fat,
                    carbs=carbs,
                    fiber=fiber,
                    date=datetime.utcnow()
                )
                session.add(log)
                success_text = (
                    f"✅ <b>Записано!</b>\n\n"
                    f"🍽️ {final_name}\n\n"
                    f"🔥 <b>{int(calories)}</b> ккал\n"
                    f"🥩 {protein:.1f} | 🥑 {fat:.1f} | 🍞 {carbs:.1f} | 🥬 {fiber:.1f}"
                )
            
            await session.commit()
            
        await state.clear()
        
        await message.answer(success_text, parse_mode="HTML")
        
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
        try: os.remove(ogg_path)
        except: pass
        
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
        try: os.remove(ogg_path)
        except: pass
        
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
