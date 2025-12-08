"""Module for product name correction handlers.

Contains:
- CorrectionStates: FSM states for correction flow
- start_correction: Show product card with field selection buttons
- Field-specific correction handlers (name, price, quantity, category)
"""
from aiogram import Bot, F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from database.base import get_db
from database.models import Product
from utils.message_cleanup import schedule_message_deletion

router = Router()

# Available product categories
CATEGORIES = [
    "Молочные продукты",
    "Мясные продукты",
    "Овощи",
    "Фрукты",
    "Снеки",
    "Бакалея",
    "Хлебобулочные изделия",
    "Напитки",
    "Сладости",
    "Замороженные продукты",
    "Консервы",
    "Прочее",
    "Корм для животных",
]


class CorrectionStates(StatesGroup):
    """FSM states for product correction flow."""

    waiting_for_name = State()
    waiting_for_price = State()
    waiting_for_quantity = State()


@router.callback_query(F.data.startswith("correct_"))
async def start_correction(callback: types.CallbackQuery, bot: Bot, state: FSMContext) -> None:
    """Handle correction button click - show product card with field selection buttons.

    Extracts product ID from callback data, loads product from database,
    and shows product card with buttons to select which field to edit.

    Args:
        callback: Telegram callback query with data format "correct_{product_id}"
        state: FSM context for storing product_id

    Returns:
        None

    """
    product_id = int(callback.data.split("_")[1])

    # Get product from DB
    async for session in get_db():
        result = await session.execute(
            select(Product).where(Product.id == product_id)
        )
        product = result.scalar_one_or_none()

        if not product:
            await callback.answer("❌ Продукт не найден", show_alert=True)
            return

        # Store product_id in state
        await state.update_data(product_id=product_id)

        # Build keyboard with field selection buttons
        builder = InlineKeyboardBuilder()
        builder.button(text="1. Название", callback_data=f"edit_name_{product_id}")
        builder.button(text="2. 💵 Цена", callback_data=f"edit_price_{product_id}")
        builder.button(text="3. Количество", callback_data=f"edit_quantity_{product_id}")
        builder.button(text="4. 🏷️ Категория", callback_data=f"edit_category_{product_id}")
        builder.adjust(2)  # 2 buttons per row

        # Send product card with edit buttons
        user_name = callback.from_user.first_name or "Пользователь"
        correction_msg = await callback.message.answer(
            f"✏️ <b>Что редактировать?</b>\n\n"
            f"▫️ <b>{product.name}</b>\n"
            f"💵 {product.price}р × {product.quantity} шт\n"
            f"🏷️ {product.category or 'Не указана'}",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        schedule_message_deletion(correction_msg, bot, user_name)
        await callback.answer()


@router.callback_query(F.data.startswith("edit_name_"))
async def start_edit_name(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Start editing product name.

    Args:
        callback: Telegram callback query with data format "edit_name_{product_id}"
        state: FSM context for storing product_id

    Returns:
        None

    """
    product_id = int(callback.data.split("_")[2])

    async for session in get_db():
        result = await session.execute(
            select(Product).where(Product.id == product_id)
        )
        product = result.scalar_one_or_none()

        if not product:
            await callback.answer("❌ Продукт не найден", show_alert=True)
            return

        await state.update_data(product_id=product_id)
        await state.set_state(CorrectionStates.waiting_for_name)

        await callback.message.answer(
            f"✏️ <b>Текущее название:</b>\n<code>{product.name}</code>\n\n"
            f"Отправьте новое название:",
            parse_mode="HTML"
        )
        await callback.answer()


@router.message(CorrectionStates.waiting_for_name)
async def apply_name_correction(message: types.Message, bot: Bot, state: FSMContext) -> None:
    """Apply name correction to the product.

    Args:
        message: Telegram message with corrected product name
        state: FSM context containing product_id

    Returns:
        None

    """
    data = await state.get_data()
    product_id = data.get("product_id")
    new_name = message.text.strip() if message.text else ""

    if not new_name:
        await message.answer("❌ Название не может быть пустым")
        return

    async for session in get_db():
        result = await session.execute(
            select(Product).where(Product.id == product_id)
        )
        product = result.scalar_one_or_none()

        if product:
            product.name = new_name
            await session.commit()

            # Send updated product card
            builder = InlineKeyboardBuilder()
            builder.button(text="✏️ Коррекция", callback_data=f"correct_{product_id}")

            user_name = message.from_user.first_name or "Пользователь"
            result_msg = await message.answer(
                f"✅ <b>Название обновлено!</b>\n\n"
                f"▫️ <b>{product.name}</b>\n"
                f"💵 {product.price}р × {product.quantity} шт\n"
                f"🏷️ {product.category or 'Не указана'}",
                reply_markup=builder.as_markup(),
                parse_mode="HTML"
            )
            schedule_message_deletion(result_msg, bot, user_name)
        else:
            await message.answer("❌ Продукт не найден")

    await state.clear()


@router.callback_query(F.data.startswith("edit_price_"))
async def start_edit_price(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Start editing product price.

    Args:
        callback: Telegram callback query with data format "edit_price_{product_id}"
        state: FSM context for storing product_id

    Returns:
        None

    """
    product_id = int(callback.data.split("_")[2])

    async for session in get_db():
        result = await session.execute(
            select(Product).where(Product.id == product_id)
        )
        product = result.scalar_one_or_none()

        if not product:
            await callback.answer("❌ Продукт не найден", show_alert=True)
            return

        await state.update_data(product_id=product_id)
        await state.set_state(CorrectionStates.waiting_for_price)

        await callback.message.answer(
            f"✏️ <b>Текущая цена:</b> {product.price}р\n\n"
            f"Отправьте новую цену (число):",
            parse_mode="HTML"
        )
        await callback.answer()


@router.message(CorrectionStates.waiting_for_price)
async def apply_price_correction(message: types.Message, bot: Bot, state: FSMContext) -> None:
    """Apply price correction to the product.

    Args:
        message: Telegram message with corrected product price
        state: FSM context containing product_id

    Returns:
        None

    """
    data = await state.get_data()
    product_id = data.get("product_id")
    price_text = message.text.strip() if message.text else ""

    try:
        new_price = float(price_text.replace(",", "."))
        if new_price < 0:
            raise ValueError("Price must be positive")
    except (ValueError, AttributeError):
        await message.answer("❌ Неверный формат цены. Отправьте число (например: 99.99)")
        return

    async for session in get_db():
        result = await session.execute(
            select(Product).where(Product.id == product_id)
        )
        product = result.scalar_one_or_none()

        if product:
            product.price = new_price
            await session.commit()

            # Send updated product card
            builder = InlineKeyboardBuilder()
            builder.button(text="✏️ Коррекция", callback_data=f"correct_{product_id}")

            user_name = message.from_user.first_name or "Пользователь"
            result_msg = await message.answer(
                f"✅ <b>Цена обновлена!</b>\n\n"
                f"▫️ <b>{product.name}</b>\n"
                f"💵 {product.price}р × {product.quantity} шт\n"
                f"🏷️ {product.category or 'Не указана'}",
                reply_markup=builder.as_markup(),
                parse_mode="HTML"
            )
            schedule_message_deletion(result_msg, bot, user_name)
        else:
            await message.answer("❌ Продукт не найден")

    await state.clear()


@router.callback_query(F.data.startswith("edit_quantity_"))
async def start_edit_quantity(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Start editing product quantity.

    Args:
        callback: Telegram callback query with data format "edit_quantity_{product_id}"
        state: FSM context for storing product_id

    Returns:
        None

    """
    product_id = int(callback.data.split("_")[2])

    async for session in get_db():
        result = await session.execute(
            select(Product).where(Product.id == product_id)
        )
        product = result.scalar_one_or_none()

        if not product:
            await callback.answer("❌ Продукт не найден", show_alert=True)
            return

        await state.update_data(product_id=product_id)
        await state.set_state(CorrectionStates.waiting_for_quantity)

        await callback.message.answer(
            f"✏️ <b>Текущее количество:</b> {product.quantity} шт\n\n"
            f"Отправьте новое количество (число):",
            parse_mode="HTML"
        )
        await callback.answer()


@router.message(CorrectionStates.waiting_for_quantity)
async def apply_quantity_correction(message: types.Message, bot: Bot, state: FSMContext) -> None:
    """Apply quantity correction to the product.

    Args:
        message: Telegram message with corrected product quantity
        state: FSM context containing product_id

    Returns:
        None

    """
    data = await state.get_data()
    product_id = data.get("product_id")
    quantity_text = message.text.strip() if message.text else ""

    try:
        new_quantity = float(quantity_text.replace(",", "."))
        if new_quantity <= 0:
            raise ValueError("Quantity must be positive")
    except (ValueError, AttributeError):
        await message.answer("❌ Неверный формат количества. Отправьте число (например: 1.5)")
        return

    async for session in get_db():
        result = await session.execute(
            select(Product).where(Product.id == product_id)
        )
        product = result.scalar_one_or_none()

        if product:
            product.quantity = new_quantity
            await session.commit()

            # Send updated product card
            builder = InlineKeyboardBuilder()
            builder.button(text="✏️ Коррекция", callback_data=f"correct_{product_id}")

            user_name = message.from_user.first_name or "Пользователь"
            result_msg = await message.answer(
                f"✅ <b>Количество обновлено!</b>\n\n"
                f"▫️ <b>{product.name}</b>\n"
                f"💵 {product.price}р × {product.quantity} шт\n"
                f"🏷️ {product.category or 'Не указана'}",
                reply_markup=builder.as_markup(),
                parse_mode="HTML"
            )
            schedule_message_deletion(result_msg, bot, user_name)
        else:
            await message.answer("❌ Продукт не найден")

    await state.clear()


@router.callback_query(F.data.startswith("edit_category_"))
async def start_edit_category(callback: types.CallbackQuery, bot: Bot, state: FSMContext) -> None:
    """Start editing product category - show category selection buttons.

    Args:
        callback: Telegram callback query with data format "edit_category_{product_id}"
        state: FSM context (not used, but required by signature)

    Returns:
        None

    """
    product_id = int(callback.data.split("_")[2])

    async for session in get_db():
        result = await session.execute(
            select(Product).where(Product.id == product_id)
        )
        product = result.scalar_one_or_none()

        if not product:
            await callback.answer("❌ Продукт не найден", show_alert=True)
            return

        # Build keyboard with category buttons
        builder = InlineKeyboardBuilder()
        for idx, category in enumerate(CATEGORIES):
            builder.button(text=category, callback_data=f"set_category_{product_id}_{idx}")
        builder.adjust(2)  # 2 buttons per row

        user_name = callback.from_user.first_name or "Пользователь"
        category_msg = await callback.message.answer(
            f"✏️ <b>Выберите категорию:</b>\n\n"
            f"Текущая: {product.category or 'Не указана'}",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        schedule_message_deletion(category_msg, bot, user_name)
        await callback.answer()


@router.callback_query(F.data.startswith("set_category_"))
async def apply_category_correction(callback: types.CallbackQuery, bot: Bot, state: FSMContext) -> None:
    """Apply category correction to the product.

    Args:
        callback: Telegram callback query with data format "set_category_{product_id}_{category_index}"
        state: FSM context (not used, but required by signature)

    Returns:
        None

    """
    parts = callback.data.split("_")
    product_id = int(parts[2])
    category_idx = int(parts[3])
    
    if category_idx < 0 or category_idx >= len(CATEGORIES):
        await callback.answer("❌ Неверная категория", show_alert=True)
        return
    
    category = CATEGORIES[category_idx]

    async for session in get_db():
        result = await session.execute(
            select(Product).where(Product.id == product_id)
        )
        product = result.scalar_one_or_none()

        if product:
            product.category = category
            await session.commit()

            # Send updated product card
            builder = InlineKeyboardBuilder()
            builder.button(text="✏️ Коррекция", callback_data=f"correct_{product_id}")

            user_name = callback.from_user.first_name or "Пользователь"
            result_msg = await callback.message.answer(
                f"✅ <b>Категория обновлена!</b>\n\n"
                f"▫️ <b>{product.name}</b>\n"
                f"💵 {product.price}р × {product.quantity} шт\n"
                f"🏷️ {product.category}",
                reply_markup=builder.as_markup(),
                parse_mode="HTML"
            )
            schedule_message_deletion(result_msg, bot, user_name)
        else:
            await callback.answer("❌ Продукт не найден", show_alert=True)
            return

    await callback.answer("✅ Категория обновлена!")
