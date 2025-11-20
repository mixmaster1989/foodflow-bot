import io
from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from FoodFlow.database.base import get_db
from FoodFlow.database.models import LabelScan, Product, ShoppingSession
from FoodFlow.services.label_ocr import LabelOCRService


router = Router()


class ShoppingMode(StatesGroup):
    scanning_labels = State()
    waiting_for_receipt = State()


@router.message(F.text == "🛒 Иду в магазин")
async def start_shopping(message: types.Message, state: FSMContext):
    session_id = None

    async for session in get_db():
        stmt = (
            select(ShoppingSession)
            .where(
                ShoppingSession.user_id == message.from_user.id,
                ShoppingSession.is_active == True,  # noqa: E712
            )
            .order_by(ShoppingSession.started_at.desc())
        )
        result = await session.execute(stmt)
        existing_session = result.scalar_one_or_none()

        if existing_session:
            session_id = existing_session.id
        else:
            new_session = ShoppingSession(user_id=message.from_user.id)
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

    await message.answer(
        "🛒 Круто! Запустил режим покупок.\n\n"
        "1. Сфотографируй этикетку товара.\n"
        "2. Отправь фото сюда — я сохраню название и КБЖУ.\n"
        "3. Когда закончишь, нажми «Я закончил покупки».",
        reply_markup=builder.as_markup()
    )


@router.message(ShoppingMode.scanning_labels, F.photo)
async def scan_label(message: types.Message, bot: Bot, state: FSMContext):
    data = await state.get_data()
    session_id = data.get("shopping_session_id")

    if not session_id:
        await message.answer("❌ Нет активной сессии покупок. Нажми «🛒 Иду в магазин».")
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
            break

        builder = InlineKeyboardBuilder()
        builder.button(text="✅ Я закончил покупки", callback_data="shopping_finish")

        await status_msg.edit_text(
            "✅ Добавлено в корзину:\n"
            f"📦 {label_data.get('name')}\n"
            f"🏷️ {label_data.get('brand') or 'Без бренда'}\n"
            f"⚖️ {label_data.get('weight') or '—'}\n"
            f"🔥 КБЖУ: {label_data.get('calories') or '—'}/"
            f"{label_data.get('protein') or '—'}/"
            f"{label_data.get('fat') or '—'}/"
            f"{label_data.get('carbs') or '—'}",
            reply_markup=builder.as_markup()
        )
    except Exception as exc:
        await status_msg.edit_text(f"❌ Ошибка при распознавании: {exc}")


@router.callback_query(F.data == "shopping_finish")
async def finish_shopping(callback: types.CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    data = await state.get_data()
    session_id = data.get("shopping_session_id")

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
async def link_label(callback: types.CallbackQuery):
    try:
        _, product_id_str, label_id_str = callback.data.split(":")
        product_id = int(product_id_str)
        label_id = int(label_id_str)
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
async def skip_label(callback: types.CallbackQuery):
    await callback.answer("Ок, оставляем как новый товар.")
    await callback.message.answer("ℹ️ Позиция помечена как новый товар. Можно скорректировать позже.")

