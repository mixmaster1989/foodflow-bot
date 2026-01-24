"""Module for receipt processing and photo handling handlers.

Contains:
- handle_photo: Main photo handler (Queued)
- process_receipt_worker: Queue worker for receipt processing
- price_tag_action: Process price tag photo
- log_food_action: Log food consumption from photo
"""
import io
import logging
from typing import Any
from datetime import datetime, timedelta

from aiogram import Bot, F, Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.base import get_db
from database.models import Product, Receipt, UserSettings
from handlers.shopping import ShoppingMode
from services.consultant import ConsultantService
from services.matching import MatchingService
from services.normalization import NormalizationService
from services.ocr import OCRService
from services.photo_queue import PhotoQueueManager
from sqlalchemy import select
from utils.message_cleanup import schedule_message_deletion

router = Router()
logger = logging.getLogger(__name__)


@router.message(F.photo, StateFilter(ShoppingMode.waiting_for_receipt))
async def handle_photo(message: types.Message, bot: Bot, state: FSMContext) -> None:
    """Handle incoming photo message.

    Routes to shopping mode if in shopping state, otherwise shows
    action menu (receipt, price tag, food log).
    
    NOW INTEGRATED WITH PHOTO QUEUE.
    """
    current_state = await state.get_state()
    user_id = message.from_user.id
    
    # 1. Shopping Mode (Priority)
    # Если в режиме сканирования этикеток - не обрабатываем здесь (shopping.router)
    if current_state in (ShoppingMode.scanning_labels.state, ShoppingMode.waiting_for_label_photo.state):
        return

    # 2. Shopping Mode: Waiting for Receipt
    if current_state == ShoppingMode.waiting_for_receipt.state:
        # Add to Queue
        logger.info(f"[PhotoFlow] Q_ADD: User {user_id} added Receipt (ShoppingMode) to queue. MsgID: {message.message_id}")
        await PhotoQueueManager.add_item(
            user_id=user_id,
            message=message,
            bot=bot,
            state=state,
            processing_func=process_receipt_worker_wrapper, # Wrapper to adapt signature
            file_id=message.photo[-1].file_id
        )
        return

    # 3. IF NO STATE -> Pass to Universal Handler!
    if current_state is None:
        return
    
    # 3. Action Menu (Default for photos)
    # We don't queue the *menu* itself, but if they choose "Receipt", we queue THAT action.
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🧾 Это чек", callback_data="action_receipt")
    builder.button(text="❄️ В холодильник", callback_data="action_add_to_fridge")
    builder.button(text="🏷️ Это ценник (сравнить)", callback_data="action_price_tag")
    builder.button(text="🍽️ Я это съел", callback_data="action_log_food")
    builder.button(text="❌ Отмена", callback_data="action_cancel")
    builder.adjust(1) 

    await message.reply(
        "📸 **Вижу фото!** Что с ним сделать?",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data == "action_cancel")
async def cancel_action(callback: types.CallbackQuery) -> None:
    """Cancel current action."""
    await callback.message.delete()
    await callback.answer("Отменено")


@router.callback_query(F.data == "action_receipt")
async def process_receipt_action(callback: types.CallbackQuery, bot: Bot, state: FSMContext) -> None:
    """Process receipt photo from action menu (Adds to Queue)."""
    photo_message = callback.message.reply_to_message
    if not photo_message or not photo_message.photo:
        await callback.message.edit_text("❌ Ошибка: не могу найти исходное фото.")
        return

    user_id = callback.from_user.id
    file_id = photo_message.photo[-1].file_id

    # UI Feedback immediately
    await callback.message.edit_text("⏳ Добавлено в очередь обработки чеков...")

    logger.info(f"[PhotoFlow] Q_ADD: User {user_id} added Receipt (MenuAction) to queue. FileID: {file_id[:10]}...")
    
    await PhotoQueueManager.add_item(
        user_id=user_id,
        message=callback.message, # Pass bot's message to edit it later
        bot=bot,
        state=state,
        processing_func=process_receipt_worker_action,
        file_id=file_id
    )
    await callback.answer()


# --- QUEUE WORKERS ---

async def process_receipt_worker_wrapper(message: types.Message, bot: Bot, state: FSMContext, file_id: str) -> None:
    """Worker for Shopping Mode (Receipt) - adapts msg signature."""
    # In shopping mode, 'message' is the user's photo message.
    # We act on it directly.
    status_msg = await message.answer("⏳ Анализирую чек (Очередь)...")
    await _process_receipt_core(message, bot, status_msg, message, state, file_id)

async def process_receipt_worker_action(message: types.Message, bot: Bot, state: FSMContext, file_id: str) -> None:
    """Worker for Menu Action - message is the BOT's status message."""
    # In menu action, 'message' is the BOT's message (which we edited to "Added to queue...").
    # We use it as status_msg.
    # We need to find the original photo info not from message (it's text), but we passed file_id.
    
    # Re-construct a dummy message object if needed for _process_receipt_core context, 
    # but _process_receipt_core mainly needs user_id and file_id.
    
    # Update status
    try:
        await message.edit_text("⏳ Анализирую чек (Начало OCR)...")
    except Exception:
        pass # Message might be deleted

    # We need a 'photo_message' context just for from_user.id usually.
    # 'message.chat.id' is the user chat (same as user_id mostly for private chats).
    
    user_id = message.chat.id
    
    await _process_receipt_core(message, bot, message, message, state, file_id, override_user_id=user_id)


# --- CORE LOGIC ---

async def _process_receipt_core(
    context_msg: types.Message,
    bot: Bot,
    status_message: types.Message,
    reply_target: types.Message,
    state: FSMContext,
    file_id: str,
    override_user_id: int | None = None
) -> None:
    """Core receipt logic run by worker."""
    user_id = override_user_id or context_msg.from_user.id
    
    logger.info(f"[PhotoFlow] OCR_START: User {user_id} processing file {file_id[:10]}...")

    try:
        # Download
        file_info = await bot.get_file(file_id)
        photo_bytes = io.BytesIO()
        await bot.download_file(file_info.file_path, photo_bytes)
        image_data = photo_bytes.getvalue()

        # OCR
        data = await OCRService.parse_receipt(image_data)
        raw_items = data.get("items", [])
        
        try:
            await status_message.edit_text(f"⏳ Чек распознан ({len(raw_items)} строк). Нормализация...")
        except:
            pass

        normalized_items = await NormalizationService.normalize_products(raw_items)
        logger.info(f"[PhotoFlow] OCR_DONE: User {user_id} found {len(normalized_items)} normalized items.")

        # 1. Save Header & Deduplicate
        receipt_id, is_duplicate = await _save_receipt_header(user_id, data)
        
        logger.info(f"[PhotoFlow] DB_SAVE: Receipt ID {receipt_id} (Duplicate={is_duplicate})")

        if is_duplicate:
             await reply_target.answer(f"⚠️ <b>Обнаружен дубликат чека!</b>\n(ID: {receipt_id})", parse_mode="HTML")

        try:
            await status_message.delete()
        except Exception:
            pass

        # 2. Update FSM - RECEIPT CACHE (MULTI-SESSION SUPPORT)
        current_data = await state.get_data()
        receipt_cache = current_data.get("receipt_cache", {}) # Format: { "receipt_id": [items...] }
        
        # Add new receipt (convert ID to str for JSON compatibility)
        receipt_cache[str(receipt_id)] = normalized_items
        
        # Prune cache: Keep last 10 receipts to prevent state bloat
        if len(receipt_cache) > 10:
             # Remove oldest keys (Python 3.7+ preserves insertion order)
             nb_to_remove = len(receipt_cache) - 10
             for _ in range(nb_to_remove):
                 try:
                     first_key = next(iter(receipt_cache))
                     del receipt_cache[first_key]
                 except:
                     pass

        await state.update_data(receipt_cache=receipt_cache)
        await state.set_state(ReceiptStates.reviewing_items)
        
        logger.info(f"[PhotoFlow] STATE_UPD: User {user_id} added Receipt {receipt_id} to cache. Total cached: {len(receipt_cache)}")

        # 3. Send Review Interface (With ID protection)
        await _send_item_review(reply_target, normalized_items, data.get("total", 0.0), receipt_id)

    except Exception as exc:
        logger.error(f"[PhotoFlow] ERROR: User {user_id} receipt processing failed: {exc}", exc_info=True)
        try:
            await status_message.edit_text(f"❌ Ошибка при обработке: {exc}")
        except:
            await reply_target.answer(f"❌ Ошибка при обработке: {exc}")


async def _save_receipt_header(user_id: int, data: dict[str, Any]) -> tuple[int, bool]:
    """Save receipt header. Returns (id, is_duplicate)."""
    total_amount = data.get("total", 0.0)
    
    async for session in get_db():
        # Check duplicate: same user, same total, last 3 mins
        time_threshold = datetime.utcnow() - timedelta(minutes=3)
        stmt = (
            select(Receipt)
            .where(
                Receipt.user_id == user_id,
                Receipt.total_amount == total_amount,
                Receipt.created_at >= time_threshold
            )
            .order_by(Receipt.id.desc())
        )
        existing = (await session.execute(stmt)).scalar_one_or_none()
        
        if existing:
            return existing.id, True

        receipt = Receipt(
            user_id=user_id,
            raw_text=str(data),
            total_amount=total_amount
        )
        session.add(receipt)
        await session.commit()
        return receipt.id, False
    return 0, False


async def _send_item_review(reply_target: types.Message, items: list[dict], total: float, receipt_id: int) -> None:
    """Send review list with SAFE CALLBACKS."""
    if not items:
        await reply_target.answer("⚠️ В чеке не найдено товаров.")
        return

    await reply_target.answer(
        f"🧾 <b>Чек #{receipt_id} обработан!</b>\n"
        f"Найдено позиций: {len(items)}\n"
        f"Сумма: {total}р\n\n"
        f"👇 <b>Проверьте список и добавьте нужное:</b>",
        parse_mode="HTML"
    )

    for idx, item in enumerate(items):
        name = item.get("name", "Unknown")
        price = item.get("price", 0.0)
        cal = item.get("calories", 0.0)
        
        builder = InlineKeyboardBuilder()
        # INCLUDE RECEIPT ID IN CALLBACK
        builder.button(text="✅ Добавить", callback_data=f"r_add_{receipt_id}_{idx}")
        builder.button(text="🗑️ Удалить", callback_data=f"r_del_{receipt_id}_{idx}")
        builder.adjust(2)

        await reply_target.answer(
            f"🔸 <b>{name}</b>\n"
            f"💵 {price}р | 🔥 ~{cal} ккал",
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🗑️ Очистить все активные чеки", callback_data="r_finish")
    await reply_target.answer("Завершить работу:", reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("r_add_"))
async def receipt_item_add(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Approve item from receipt (Uses Cache for Multi-Session)."""
    try:
        parts = callback.data.split("_")
        # Format: r_add_{receipt_id}_{idx}
        
        if len(parts) < 4:
            await callback.answer("⚠️ Кнопка устарела (формат).", show_alert=True)
            return
            
        btn_receipt_id_str = parts[2] # String key for dict lookup
        idx = int(parts[3])
        
        data = await state.get_data()
        receipt_cache = data.get("receipt_cache", {})


        # 1. Validation Logic
        if btn_receipt_id_str not in receipt_cache:
            await callback.answer(
                f"🚫 Чек #{btn_receipt_id_str} устарел.\n\n"
                f"Я хранил его, но место кончилось (последние 10 чеков) или сессия была сброшена.", 
                show_alert=True
            )
            return

        items = receipt_cache[btn_receipt_id_str]

        if idx >= len(items):
            await callback.answer("❌ Товар не найден в списке.", show_alert=True)
            return
        
        item = items[idx]
        
        # 2. Save
        async for session in get_db():
            product = Product(
                receipt_id=int(btn_receipt_id_str),
                name=item.get("name", "Unknown"),
                price=item.get("price", 0.0),
                quantity=item.get("quantity", 1.0),
                category=item.get("category", "Uncategorized"),
                calories=item.get("calories", 0.0),
                protein=item.get("protein", 0.0),
                fat=item.get("fat", 0.0),
                carbs=item.get("carbs", 0.0),
                fiber=item.get("fiber", 0.0), # SAVE PROCESSED FIBER
                user_id=callback.from_user.id
            )
            session.add(product)
            await session.commit()
            logger.info(f"[PhotoFlow] ITEM_SAVED: User {callback.from_user.id} added '{product.name}' from Receipt {btn_receipt_id_str} (Fiber: {item.get('fiber', 0.0)})")

        # 3. UI Update
        await callback.message.edit_text(
            f"✅ <b>Добавлено: {item.get('name')}</b>",
            parse_mode="HTML", 
            reply_markup=None
        )
        await callback.answer("Добавлено!")

    except Exception as e:
        logger.error(f"Add item error: {e}", exc_info=True)
        await callback.answer(f"Ошибка: {e}", show_alert=True)


@router.callback_query(F.data.startswith("r_del_"))
async def receipt_item_del(callback: types.CallbackQuery) -> None:
    """Delete item (Visual only, no strict check needed but good practice)."""
    await callback.message.edit_text(f"🗑️ <b>Удалено</b>", parse_mode="HTML", reply_markup=None)
    await callback.answer("Удалено")


@router.callback_query(F.data == "r_finish")
async def receipt_finish(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Finish receipt review (Clears ALL cache)."""
    await state.clear()
    await callback.message.edit_text("✅ <b>Все активные сессии чеков закрыты.</b>", parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "action_price_tag")
async def price_tag_action(callback: types.CallbackQuery, bot: Bot) -> None:
    """Process price tag photo."""
    photo_message = callback.message.reply_to_message
    if not photo_message or not photo_message.photo:
        await callback.message.edit_text("❌ Ошибка: не могу найти исходное фото.")
        return

    status_msg = await callback.message.edit_text("⏳ Анализирую ценник...")

    try:
        photo = photo_message.photo[-1]
        file_info = await bot.get_file(photo.file_id)
        photo_bytes = io.BytesIO()
        await bot.download_file(file_info.file_path, photo_bytes)

        from database.models import PriceTag
        from services.price_search import PriceSearchService
        from services.price_tag_ocr import PriceTagOCRService
        from rapidfuzz import fuzz
        
        price_data = await PriceTagOCRService.parse_price_tag(photo_bytes.getvalue())

        if not price_data or not price_data.get("product_name") or not price_data.get("price"):
            await status_msg.edit_text("❌ Не удалось распознать ценник.")
            return

        async for session in get_db():
            price_tag = PriceTag(
                user_id=photo_message.from_user.id,
                product_name=price_data.get("product_name"),
                volume=price_data.get("volume"),
                price=float(price_data.get("price")),
                store_name=price_data.get("store"),
                photo_date=datetime.fromisoformat(price_data["date"]) if price_data.get("date") else None,
            )
            session.add(price_tag)
            await session.commit()
            break

        await status_msg.edit_text(f"✅ Ценник сохранен: {price_data.get('product_name')} - {price_data.get('price')}р")

    except Exception as exc:
        await status_msg.edit_text(f"❌ Ошибка: {exc}")


class ReceiptStates(StatesGroup):
    waiting_for_portion_weight = State()
    editing_food_name = State()
    reviewing_items = State()
    confirming_manual_add = State()


@router.callback_query(F.data == "action_log_food")
async def log_food_action(callback: types.CallbackQuery, bot: Bot, state: FSMContext) -> None:
    """Log food consumption - ISOLATED BY FILE_ID."""
    photo_message = callback.message.reply_to_message
    if not photo_message or not photo_message.photo:
        await callback.message.edit_text("❌ Ошибка: не могу найти исходное фото.")
        return
    
    status_msg = await callback.message.edit_text("⏳ Анализирую блюдо...")
    
    try:
        photo = photo_message.photo[-1]
        file_id = photo.file_id
        # BUG FIX: Use LAST 16 chars (unique part), not FIRST 12 (common prefix)
        file_id_short = file_id[-16:]
        
        file_info = await bot.get_file(file_id)
        photo_bytes = io.BytesIO()
        await bot.download_file(file_info.file_path, photo_bytes)
        
        from services.ai import AIService
        product_data = await AIService.recognize_product_from_image(photo_bytes.getvalue())
        
        if not product_data or not product_data.get("name"):
            product_data = {"name": "Неизвестное блюдо", "calories": 200, "protein": 10, "fat": 10, "carbs": 20, "fiber": 0}
        
        # ISOLATED STORAGE: Store in pending_foods dict by file_id
        current_data = await state.get_data()
        pending_foods = current_data.get("pending_foods", {})
        pending_foods[file_id_short] = product_data
        
        # Prune old entries (keep max 20)
        if len(pending_foods) > 20:
            keys = list(pending_foods.keys())
            for old_key in keys[:-20]:
                del pending_foods[old_key]
        
        await state.update_data(
            pending_foods=pending_foods,
            active_food_id=file_id_short  # Track which food is currently being weighed
        )
        await state.set_state(ReceiptStates.waiting_for_portion_weight)
        
        builder = InlineKeyboardBuilder()
        # Two clear options per user feedback
        builder.button(text="🍽️ Средняя порция (300г)", callback_data=f"food_no_scale:{file_id_short}")
        builder.button(text="✏️ Изменить название", callback_data=f"food_edit_name:{file_id_short}")
        builder.button(text="❌ Отмена", callback_data="action_cancel")
        builder.adjust(1)
        
        logger.info(f"[FoodLog] User {callback.from_user.id} recognized '{product_data['name']}' (ID: {file_id_short})")
        
        await status_msg.edit_text(
            f"🍽️ <b>{product_data['name']}</b>\n\n"
            f"📏 <b>Введите вес в граммах</b> (например: 150)\n\n"
            f"Или нажмите кнопку:",
            parse_mode="HTML", reply_markup=builder.as_markup()
        )
    except Exception as e:
        logger.error(f"[FoodLog] Error: {e}", exc_info=True)
        await status_msg.edit_text(f"Ошибка: {e}")


@router.callback_query(F.data.startswith("food_no_scale:"))
async def log_food_no_scale(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Handle 'no scale' button - uses file_id from callback."""
    parts = callback.data.split(":")
    if len(parts) < 2:
        await callback.answer("⚠️ Кнопка устарела.", show_alert=True)
        return
    
    file_id_short = parts[1]
    
    data = await state.get_data()
    pending_foods = data.get("pending_foods", {})
    product_data = pending_foods.get(file_id_short)
    
    if not product_data:
        await callback.answer("⚠️ Данные о блюде не найдены (возможно, устарели).", show_alert=True)
        return
    
    await _save_consumption(callback.message, callback.from_user.id, product_data, 300.0)
    
    # Clean up this entry
    if file_id_short in pending_foods:
        del pending_foods[file_id_short]
        await state.update_data(pending_foods=pending_foods)
    
    await state.set_state(None)  # Clear state but keep pending_foods
    
    # Show button to add weight to other pending foods if any left
    if pending_foods:
        builder = InlineKeyboardBuilder()
        builder.button(text=f"📏 Указать вес ({len(pending_foods)} ещё)", callback_data="list_pending_foods")
        builder.button(text="🏠 Меню", callback_data="main_menu")
        builder.adjust(1)
        await callback.message.answer(
            f"✅ Записано!\n\n<i>Осталось {len(pending_foods)} фото без веса.</i>",
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
    else:
        await callback.answer("✅ Записано!")


@router.callback_query(F.data.startswith("food_edit_name:"))
async def edit_food_name_start(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Start editing food name."""
    parts = callback.data.split(":")
    if len(parts) < 2:
        await callback.answer("⚠️ Ошибка", show_alert=True)
        return
    
    file_id_short = parts[1]
    await state.update_data(editing_food_id=file_id_short)
    await state.set_state(ReceiptStates.editing_food_name)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="action_cancel")
    
    await callback.message.edit_text(
        "✏️ <b>Введите правильное название блюда:</b>\n\n"
        "<i>Например: Горбуша, Творог 5%, Салат Цезарь</i>",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.message(ReceiptStates.editing_food_name)
async def edit_food_name_input(message: types.Message, state: FSMContext) -> None:
    """Handle new food name input and recalculate KBJU."""
    data = await state.get_data()
    file_id_short = data.get("editing_food_id")
    pending_foods = data.get("pending_foods", {})
    
    if not file_id_short or file_id_short not in pending_foods:
        await message.answer("⚠️ Данные устарели. Отправьте фото заново.")
        await state.clear()
        return
    
    new_name = message.text.strip()
    
    # Get KBJU for new name from AI
    from services.normalization import NormalizationService
    normalizer = NormalizationService()
    
    status_msg = await message.answer("🔄 Ищу данные о продукте...")
    
    try:
        enriched = await normalizer.normalize_products([{"name": new_name}])
        if enriched and len(enriched) > 0:
            product_data = enriched[0]
            product_data["name"] = new_name
        else:
            # Fallback - keep old KBJU but change name
            product_data = pending_foods[file_id_short]
            product_data["name"] = new_name
        
        # Update pending foods
        pending_foods[file_id_short] = product_data
        await state.update_data(pending_foods=pending_foods, active_food_id=file_id_short)
        await state.set_state(ReceiptStates.waiting_for_portion_weight)
        
        builder = InlineKeyboardBuilder()
        builder.button(text="🍽️ Средняя порция (300г)", callback_data=f"food_no_scale:{file_id_short}")
        builder.button(text="✏️ Изменить название", callback_data=f"food_edit_name:{file_id_short}")
        builder.button(text="❌ Отмена", callback_data="action_cancel")
        builder.adjust(1)
        
        await status_msg.edit_text(
            f"🍽️ <b>{product_data['name']}</b>\n\n"
            f"<b>Напишите вес в граммах</b> (например: 150)\n\n"
            f"Или выберите действие:",
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
    except Exception as e:
        logger.error(f"Error editing food name: {e}")
        await status_msg.edit_text(f"❌ Ошибка: {e}")


@router.message(ReceiptStates.waiting_for_portion_weight)
async def log_food_weight_input(message: types.Message, state: FSMContext) -> None:
    """Handle weight input - uses active_food_id from state."""
    current_state = await state.get_state()
    logger.info(f"[FoodLog] Weight input received: '{message.text}' from user {message.from_user.id}, state={current_state}")
    
    data = await state.get_data()
    active_food_id = data.get("active_food_id")
    pending_foods = data.get("pending_foods", {})
    
    logger.info(f"[FoodLog] active_food_id={active_food_id}, pending_foods_keys={list(pending_foods.keys())}")
    
    if not active_food_id or active_food_id not in pending_foods:
        logger.warning(f"[FoodLog] Weight input but no active food. User {message.from_user.id}, active_id={active_food_id}")
        await message.answer("⚠️ Не могу найти блюдо для записи. Попробуйте снова отправить фото.")
        await state.set_state(None)
        return
    
    try:
        weight = float(message.text.replace(",", ".").strip())
        if weight <= 0:
            await message.answer("❌ Введите положительное число.")
            return
            
        product_data = pending_foods[active_food_id]
        await _save_consumption(message, message.from_user.id, product_data, weight)
        
        # Clean up
        del pending_foods[active_food_id]
        await state.update_data(pending_foods=pending_foods, active_food_id=None)
        await state.set_state(None)
        
    except ValueError:
        await message.answer("❌ Введите число (например: 150 или 200.5)")

async def _save_consumption(reply_target: types.Message, user_id: int, product_data: dict, weight: float) -> None:
    """Helper to save consumption log."""
    from database.models import ConsumptionLog
    factor = weight / 100.0
    cal = float(product_data.get("calories", 0) or 0) * factor
    async for session in get_db():
        log = ConsumptionLog(
            user_id=user_id,
            product_name=product_data.get("name", "Еда"),
            calories=cal,
            protein=float(product_data.get("protein", 0) or 0) * factor,
            fat=float(product_data.get("fat", 0) or 0) * factor,
            carbs=float(product_data.get("carbs", 0) or 0) * factor,
            fiber=float(product_data.get("fiber", 0) or 0) * factor, # SAVE PROCESSED FIBER
            date=datetime.utcnow()
        )
        session.add(log)
        await session.commit()
    
    try:
        text = f"✅ Записано: {product_data.get('name')} ({int(weight)}г, {int(cal)} ккал)"
        if reply_target.from_user.is_bot:
             await reply_target.edit_text(text)
        else:
             await reply_target.answer(text)
    except:
        pass


@router.callback_query(F.data == "action_add_to_fridge")
async def add_to_fridge_action(callback: types.CallbackQuery, bot: Bot, state: FSMContext) -> None:
    """Add product to fridge from global photo action."""
    photo_message = callback.message.reply_to_message
    if not photo_message or not photo_message.photo:
        await callback.message.edit_text("❌ Ошибка.")
        return

    status_msg = await callback.message.edit_text("⏳ Анализирую...")
    try:
        file_id = photo_message.photo[-1].file_id
        
        from services.ai import AIService
        file_info = await bot.get_file(file_id)
        photo_bytes = io.BytesIO()
        await bot.download_file(file_info.file_path, photo_bytes)
        
        product_data = await AIService.recognize_product_from_image(photo_bytes.getvalue())
        
        if not product_data:
             await status_msg.edit_text("❌ Не распознано.")
             return

        await state.update_data(manual_product=product_data)
        await state.set_state(ReceiptStates.confirming_manual_add)
        
        builder = InlineKeyboardBuilder()
        builder.button(text="✅ Добавить", callback_data="manual_confirm")
        builder.button(text="❌ Отмена", callback_data="manual_cancel")
        builder.adjust(2)
        
        await status_msg.edit_text(
            f"Добавить {product_data.get('name')}?\n{product_data.get('calories')} ккал\n(Kлетчатка: {product_data.get('fiber', 0)}г)", 
            reply_markup=builder.as_markup()
        )
        
    except Exception as e:
        await status_msg.edit_text(f"Ошибка: {e}")


@router.callback_query(ReceiptStates.confirming_manual_add, F.data == "manual_confirm")
async def manual_add_confirm(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Confirm manual add."""
    data = await state.get_data()
    product_data = data.get("manual_product")
    if product_data:
        async for session in get_db():
            product = Product(
                user_id=callback.from_user.id, 
                source="manual_chat", 
                name=product_data.get("name", "Продукт"), 
                calories=float(product_data.get("calories") or 0),
                protein=float(product_data.get("protein") or 0),
                fat=float(product_data.get("fat") or 0),
                carbs=float(product_data.get("carbs") or 0),
                fiber=float(product_data.get("fiber") or 0),
                price=0.0
            )
            session.add(product)
            await session.commit()
    await state.clear()
    await callback.message.edit_text("✅ Добавлено!")
    await callback.answer()


@router.callback_query(ReceiptStates.confirming_manual_add, F.data == "manual_cancel")
async def manual_add_cancel(callback: types.CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("❌ Отменено")
    await callback.answer()


@router.callback_query(F.data == "list_pending_foods")
async def list_pending_foods(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Show list of pending foods that need weight input."""
    data = await state.get_data()
    pending_foods = data.get("pending_foods", {})
    
    if not pending_foods:
        await callback.answer("Нет фото, ожидающих ввода веса.", show_alert=True)
        return
    
    builder = InlineKeyboardBuilder()
    text = "📏 <b>Выберите продукт для ввода веса:</b>\n\n"
    
    for file_id, product_data in pending_foods.items():
        name = product_data.get("name", "Продукт")[:25]
        cal_100 = int(product_data.get("calories", 0) or 0)
        text += f"▫️ {name} ({cal_100} ккал/100г)\n"
        builder.button(text=f"📏 {name}", callback_data=f"select_pending:{file_id}")
    
    builder.button(text="🔙 В меню", callback_data="main_menu")
    builder.adjust(1)
    
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("select_pending:"))
async def select_pending_food(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Select a pending food to enter weight for."""
    file_id_short = callback.data.split(":")[1]
    
    data = await state.get_data()
    pending_foods = data.get("pending_foods", {})
    product_data = pending_foods.get(file_id_short)
    
    if not product_data:
        await callback.answer("⚠️ Продукт не найден (возможно, устарел).", show_alert=True)
        return
    
    await state.update_data(active_food_id=file_id_short)
    await state.set_state(ReceiptStates.waiting_for_portion_weight)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🍽️ Средняя порция (300г)", callback_data=f"food_no_scale:{file_id_short}")
    builder.button(text="🔙 К списку", callback_data="list_pending_foods")
    builder.adjust(1)
    
    name = product_data.get("name", "Продукт")
    cal_100 = int(product_data.get("calories", 0) or 0)
    
    await callback.message.edit_text(
        f"🍽️ <b>{name}</b>\n"
        f"<i>{cal_100} ккал на 100г</i>\n\n"
        f"📏 <b>Введите вес в граммах</b> (например: 150)",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await callback.answer()
