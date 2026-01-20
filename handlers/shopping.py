"""Module for shopping mode handlers (AR shopping assistance).

Contains:
- ShoppingMode: FSM states for shopping flow
- start_shopping: Initialize shopping session
- scan_label: Process product label photo
- finish_shopping: Complete shopping and match products
- link_label: Link scanned label to product
- skip_label: Skip label matching
- cancel_shopping_session: Cancel current shopping session
- delete_scan: Delete scanned label
"""
import io

from aiogram import Bot, F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from database.base import get_db
from database.models import LabelScan, Product, ShoppingSession, UserSettings
from services.consultant import ConsultantService
from services.label_ocr import LabelOCRService

router = Router()


class ShoppingMode(StatesGroup):
    """FSM states for shopping mode flow."""

    scanning_labels = State()
    waiting_for_receipt = State()
    waiting_for_label_photo = State()  # Waiting for label photo for specific product


@router.callback_query(F.data == "start_shopping_mode")
async def start_shopping(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Initialize shopping session.

    Creates or reuses active shopping session and sets FSM state
    to scanning_labels.

    Args:
        callback: Telegram callback query
        state: FSM context

    Returns:
        None

    """
    message = callback.message
    session_id = None

    async for session in get_db():
        stmt = (
            select(ShoppingSession)
            .where(
                ShoppingSession.user_id == callback.from_user.id,
                ShoppingSession.is_active == True,  # noqa: E712
            )
            .order_by(ShoppingSession.started_at.desc())
        )
        result = await session.execute(stmt)
        existing_session = result.scalar_one_or_none()

        if existing_session:
            session_id = existing_session.id
        else:
            new_session = ShoppingSession(user_id=callback.from_user.id)
            session.add(new_session)
            await session.commit()
            await session.refresh(new_session)
            session_id = new_session.id

        break

    if not session_id:
        await message.answer("❌ Не удалось создать сессию покупок. Попробуй позже.")
        return

    await state.set_state(ShoppingMode.scanning_labels)
    await state.update_data(shopping_session_id=session_id)

    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Я закончил покупки", callback_data="shopping_finish")
    builder.button(text="❌ Отменить покупки", callback_data="shopping_cancel_session")
    builder.adjust(1)

    # Image path
    photo_path = types.FSInputFile("assets/shopping_mode.png")

    caption = (
        "🛒 <b>Режим покупок</b>\n\n"
        "1. Сфотографируй этикетку товара.\n"
        "2. Отправь фото сюда — я сохраню название и КБЖУ.\n"
        "3. Когда закончишь, нажми «Я закончил покупки»."
    )

    # Try to edit if possible (if previous was photo), otherwise send new
    try:
        await message.edit_media(
            media=types.InputMediaPhoto(media=photo_path, caption=caption, parse_mode="HTML"),
            reply_markup=builder.as_markup()
        )
    except Exception:
        # If edit fails (e.g. previous was text), delete and send new photo
        await message.delete()
        await message.answer_photo(
            photo=photo_path,
            caption=caption,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )

    await callback.answer()


@router.message(ShoppingMode.scanning_labels, F.photo)
async def scan_label(message: types.Message, bot: Bot, state: FSMContext) -> None:
    data = await state.get_data()
    session_id = data.get("shopping_session_id")

    if not session_id:
        await message.answer("❌ Нет активной сессии покупок. Нажми «🛒 Иду в магазин».")
        return

    from services.photo_queue import PhotoQueueManager
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"DEBUG TIMING: calling add_item for {message.from_user.id}")
    await PhotoQueueManager.add_item(
        user_id=message.from_user.id,
        message=message,
        bot=bot,
        state=state,
        processing_func=process_single_label_shopping,
        file_id=message.photo[-1].file_id
    )
    logger.info(f"DEBUG TIMING: returned from add_item for {message.from_user.id}")

async def process_single_label_shopping(message: types.Message, bot: Bot, state: FSMContext, file_id: str) -> None:
    """Worker function for processing a single label in shopping mode."""
    data = await state.get_data()
    session_id = data.get("shopping_session_id")
    # Note: state data might persist, but if flow canceled it might be stale.
    # But usually queue processes fast enough or we check validity.
    
    if not session_id:
        # Should checked inside worker? 
        # Actually state might satisfy even if session cancelled?
        pass

    status_msg = await message.answer("⏳ Сканирую этикетку...")

    try:
        file_info = await bot.get_file(file_id)
        photo_bytes = io.BytesIO()
        await bot.download_file(file_info.file_path, photo_bytes)

        label_data = await LabelOCRService.parse_label(photo_bytes.getvalue())
        if not label_data or not label_data.get("name"):
            raise ValueError("Не удалось распознать название товара.")

        async for session in get_db():
            scan = LabelScan(
                session_id=session_id,
                name=label_data.get("name", "Неизвестный товар"),
                brand=label_data.get("brand"),
                weight=label_data.get("weight"),
                calories=label_data.get("calories"),
                protein=label_data.get("protein"),
                fat=label_data.get("fat"),
                carbs=label_data.get("carbs"),
            )
            session.add(scan)
            await session.commit()
            
            # Get consultant recommendations
            settings_stmt = select(UserSettings).where(UserSettings.user_id == message.from_user.id)
            settings_result = await session.execute(settings_stmt)
            settings = settings_result.scalar_one_or_none()

            recommendation_text = ""
            if settings and settings.is_initialized:
                # Create temporary Product object for analysis
                temp_product = Product(
                    name=label_data.get("name", "Неизвестный товар"),
                    calories=float(label_data.get("calories", 0) or 0),
                    protein=float(label_data.get("protein", 0) or 0),
                    fat=float(label_data.get("fat", 0) or 0),
                    carbs=float(label_data.get("carbs", 0) or 0),
                    category=None,
                    price=0.0,
                    quantity=1.0
                )
                recommendations = await ConsultantService.analyze_product(
                    temp_product, settings, context="shopping"
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

        builder = InlineKeyboardBuilder()
        builder.button(text="✅ Я закончил покупки", callback_data="shopping_finish")
        builder.button(text="🗑️ Удалить этот товар", callback_data=f"shopping_delete_scan:{scan.id}")
        builder.adjust(1)

        await status_msg.edit_text(
            "✅ Добавлено в корзину:\n"
            f"📦 {label_data.get('name')}\n"
            f"🏷️ {label_data.get('brand') or 'Без бренда'}\n"
            f"⚖️ {label_data.get('weight') or '—'}\n"
            f"🔥 КБЖУ: {label_data.get('calories') or '—'}/"
            f"{label_data.get('protein') or '—'}/"
            f"{label_data.get('fat') or '—'}/"
            f"{label_data.get('carbs') or '—'}"
            + recommendation_text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    except Exception as exc:
        await status_msg.edit_text(f"❌ Ошибка при распознавании: {exc}")


@router.callback_query(F.data == "shopping_finish")
async def finish_shopping(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Finish shopping session and request receipt.

    Switches to waiting_for_receipt state to match scanned labels
    with receipt products.

    Args:
        callback: Telegram callback query
        state: FSM context containing shopping_session_id

    Returns:
        None

    """
    current_state = await state.get_state()
    data = await state.get_data()
    session_id: int | None = data.get("shopping_session_id")

    if current_state != ShoppingMode.scanning_labels.state or not session_id:
        await callback.answer("Нет активной сессии покупок.", show_alert=True)
        return

    await state.set_state(ShoppingMode.waiting_for_receipt)

    await callback.message.answer(
        "👌 Отлично! Теперь сфотографируй чек и отправь его сюда. "
        "Я сопоставлю позиции с этикетками."
    )
    await callback.answer()


@router.callback_query(F.data.startswith("sm_link:"))
async def link_label(callback: types.CallbackQuery) -> None:
    """Manually link scanned label to product.

    Args:
        callback: Telegram callback query with data format "sm_link:{product_id}:{label_id}"

    Returns:
        None

    """
    try:
        _, product_id_str, label_id_str = callback.data.split(":")
        product_id: int = int(product_id_str)
        label_id: int = int(label_id_str)
    except (ValueError, AttributeError):
        await callback.answer("Некорректные данные.", show_alert=True)
        return

    linked_product = None
    linked_label = None

    async for session in get_db():
        product = await session.get(Product, product_id)
        label = await session.get(LabelScan, label_id)

        if not product or not label:
            await callback.answer("Элемент не найден.", show_alert=True)
            return

        shopping_session = await session.get(ShoppingSession, label.session_id)
        if not shopping_session or shopping_session.user_id != callback.from_user.id:
            await callback.answer("Нет доступа к этой позиции.", show_alert=True)
            return

        label.matched_product_id = product.id

        if label.calories is not None:
            product.calories = float(label.calories)
        if label.protein is not None:
            product.protein = float(label.protein)
        if label.fat is not None:
            product.fat = float(label.fat)
        if label.carbs is not None:
            product.carbs = float(label.carbs)

        await session.commit()
        linked_product = product
        linked_label = label
        break

    if not linked_product or not linked_label:
        await callback.answer("Не удалось сопоставить.", show_alert=True)
        return

    await callback.message.answer(
        "✅ Сопоставлено вручную:\n"
        f"📄 {linked_product.name}\n"
        f"📦 {linked_label.name}"
    )
    await callback.answer("Готово!")


@router.callback_query(F.data.startswith("sm_skip:"))
async def skip_label(callback: types.CallbackQuery) -> None:
    """Skip label matching and mark product as new.

    Args:
        callback: Telegram callback query

    Returns:
        None

    """
    await callback.answer("Ок, оставляем как новый товар.")
    await callback.message.answer("ℹ️ Позиция помечена как новый товар. Можно скорректировать позже.")


@router.callback_query(F.data.startswith("sm_request_label:"))
async def request_label_photo(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Request label photo for unmatched product.

    Sets FSM state to waiting_for_label_photo and asks user to send photo.

    Args:
        callback: Telegram callback query with data format "sm_request_label:{product_id}"
        state: FSM context

    Returns:
        None

    """
    try:
        product_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer("Ошибка данных", show_alert=True)
        return

    # Get product info
    async for session in get_db():
        product = await session.get(Product, product_id)
        if not product:
            await callback.answer("Товар не найден", show_alert=True)
            return
        product_name = product.name
        break

    await state.set_state(ShoppingMode.waiting_for_label_photo)
    await state.update_data(waiting_product_id=product_id)

    await callback.message.edit_text(
        f"📸 <b>Отправь фото этикетки</b>\n\n"
        f"📄 Товар: {product_name}\n\n"
        f"Сфотографируй этикетку этого товара и отправь фото.",
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("sm_remove_product:"))
async def remove_product(callback: types.CallbackQuery) -> None:
    """Remove unmatched product from database.

    Args:
        callback: Telegram callback query with data format "sm_remove_product:{product_id}"

    Returns:
        None

    """
    try:
        product_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer("Ошибка данных", show_alert=True)
        return

    async for session in get_db():
        product = await session.get(Product, product_id)
        if not product:
            await callback.answer("Товар не найден", show_alert=True)
            return

        product_name = product.name
        await session.delete(product)
        await session.commit()
        break

    await callback.message.edit_text(f"🗑️ Товар '{product_name}' удален из списка.")
    await callback.answer("Товар удален")


@router.message(ShoppingMode.waiting_for_label_photo, F.photo)
async def process_label_photo_for_product(message: types.Message, bot: Bot, state: FSMContext) -> None:
    """Process label photo for specific unmatched product.

    Extracts product info from label and links it to the product.

    Args:
        message: Telegram message with label photo
        bot: Telegram bot instance
        state: FSM context containing waiting_product_id

    Returns:
        None

    """
    data = await state.get_data()
    product_id = data.get("waiting_product_id")

    if not product_id:
        await message.answer("❌ Ошибка: не найден товар для обработки.")
        await state.clear()
        return

    status_msg = await message.answer("⏳ Сканирую этикетку...")

    try:
        photo = message.photo[-1]
        file_info = await bot.get_file(photo.file_id)
        photo_bytes = io.BytesIO()
        await bot.download_file(file_info.file_path, photo_bytes)

        label_data = await LabelOCRService.parse_label(photo_bytes.getvalue())
        if not label_data or not label_data.get("name"):
            raise ValueError("Не удалось распознать название товара.")

        async for session in get_db():
            product = await session.get(Product, product_id)
            if not product:
                await status_msg.edit_text("❌ Товар не найден.")
                await state.clear()
                return

            # Update product with label data
            if label_data.get("calories") is not None:
                product.calories = float(label_data.get("calories"))
            if label_data.get("protein") is not None:
                product.protein = float(label_data.get("protein"))
            if label_data.get("fat") is not None:
                product.fat = float(label_data.get("fat"))
            if label_data.get("carbs") is not None:
                product.carbs = float(label_data.get("carbs"))

            await session.commit()
            break

        await status_msg.edit_text(
            "✅ <b>Этикетка обработана!</b>\n\n"
            f"📄 {product.name}\n"
            f"📦 {label_data.get('name')}\n"
            f"🔥 КБЖУ: {label_data.get('calories') or '—'}/"
            f"{label_data.get('protein') or '—'}/"
            f"{label_data.get('fat') or '—'}/"
            f"{label_data.get('carbs') or '—'}",
            parse_mode="HTML"
        )
        await state.clear()

    except Exception as exc:
        await status_msg.edit_text(f"❌ Ошибка при распознавании: {exc}")
        await state.clear()


from handlers.menu import show_main_menu


@router.callback_query(F.data == "shopping_cancel_session")
async def cancel_shopping_session(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Cancel current shopping session.

    Marks session as inactive and clears FSM state.

    Args:
        callback: Telegram callback query
        state: FSM context

    Returns:
        None

    """
    data = await state.get_data()
    session_id = data.get("shopping_session_id")

    if session_id:
        async for session in get_db():
            shopping_session = await session.get(ShoppingSession, session_id)
            if shopping_session:
                shopping_session.is_active = False
                await session.commit()
            break

    await state.clear()
    await callback.answer("Сессия отменена")
    await show_main_menu(callback.message, callback.from_user.first_name, callback.from_user.id)


@router.callback_query(F.data.startswith("shopping_delete_scan:"))
async def delete_scan(callback: types.CallbackQuery) -> None:
    """Delete scanned label from shopping session.

    Args:
        callback: Telegram callback query with data format "shopping_delete_scan:{label_id}"

    Returns:
        None

    """
    try:
        scan_id = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.answer("Ошибка данных", show_alert=True)
        return

    async for session in get_db():
        scan = await session.get(LabelScan, scan_id)
        if scan:
            await session.delete(scan)
            await session.commit()
            await callback.message.edit_text(f"🗑️ Товар '{scan.name}' удален из списка.")
            await callback.answer("Товар удален")
        else:
            await callback.message.edit_text("❌ Товар уже удален или не найден.")
            await callback.answer("Не найдено", show_alert=True)
        break

