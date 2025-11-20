import io
import logging
import math
from aiogram import Router, F, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, select
from FoodFlow.database.base import get_db
from FoodFlow.database.models import Product, Receipt, ConsumptionLog
from datetime import datetime

router = Router()
logger = logging.getLogger(__name__)

PAGE_SIZE = 12


@router.message(F.text == "🧊 Холодильник")
async def show_fridge(message: types.Message):
    user_id = message.from_user.id
    logger.info("User %s requested fridge overview", user_id)

    total_items = await _get_total_products(user_id)
    if total_items == 0:
        await message.answer("В холодильнике пусто! 🕸️\nСкинь фото чека, чтобы пополнить запасы.")
        return

    summary_text = await _build_summary_text(user_id, total_items)
    await message.answer(summary_text, parse_mode="HTML")

    page_message = await message.answer("Загружаю содержимое холодильника...")
    await _update_fridge_page(page_message, user_id, page=0, forced_total=total_items)


@router.callback_query(F.data.startswith("fridge_page:"))
async def paginate_fridge(callback: types.CallbackQuery):
    try:
        page = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.answer("Некорректная страница", show_alert=True)
        return

    total_items = await _get_total_products(callback.from_user.id)
    if total_items == 0:
        await callback.message.edit_text("Холодильник пуст.")
        await callback.answer()
        return

    await _update_fridge_page(callback.message, callback.from_user.id, page=page, forced_total=total_items)
    await callback.answer()


@router.callback_query(F.data == "fridge_export")
async def export_fridge(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    logger.info("User %s requested fridge export", user_id)

    async for session in get_db():
        stmt = (
            select(Product)
            .join(Receipt)
            .where(Receipt.user_id == user_id)
            .order_by(Product.id.desc())
        )
        products = (await session.execute(stmt)).scalars().all()

    if not products:
        await callback.answer("Холодильник пуст.", show_alert=True)
        return

    lines = ["Название;Кол-во;Цена;Категория"]
    for product in products:
        lines.append(
            f"{product.name};{product.quantity};{product.price};{product.category or '—'}"
        )

    csv_content = "\n".join(lines)
    file_bytes = csv_content.encode("utf-8")
    document = types.BufferedInputFile(file_bytes, filename="fridge_export.csv")
    await callback.message.answer_document(document, caption="Экспорт холодильника (CSV)")
    await callback.answer("Экспорт готов!")


@router.callback_query(F.data.startswith("eat_"))
async def eat_product(callback: types.CallbackQuery):
    try:
        product_id = int(callback.data.split("_")[1])
    except (IndexError, ValueError):
        await callback.answer("Ошибка", show_alert=True)
        return
    
    async for session in get_db():
        product = await session.get(Product, product_id)
        if not product:
            await callback.answer("Продукт не найден", show_alert=True)
            return
        
        # Log consumption
        log = ConsumptionLog(
            user_id=callback.from_user.id,
            product_name=product.name,
            calories=product.calories,
            protein=product.protein,
            fat=product.fat,
            carbs=product.carbs,
            date=datetime.utcnow()
        )
        session.add(log)
        
        # Decrease quantity or delete
        if product.quantity > 1:
            product.quantity -= 1
        else:
            await session.delete(product)
        
        await session.commit()
        product_name = product.name
        break
    
    await callback.answer(f"✅ Съел {product_name}!")
    # Refresh page
    total = await _get_total_products(callback.from_user.id)
    if total > 0:
        await _update_fridge_page(callback.message, callback.from_user.id, page=0, forced_total=total)
    else:
        await callback.message.edit_text("Холодильник пуст! 🕸️")


async def _get_total_products(user_id: int) -> int:
    async for session in get_db():
        total = await session.scalar(
            select(func.count())
            .select_from(Product)
            .join(Receipt)
            .where(Receipt.user_id == user_id)
        )
        return total or 0
    return 0


async def _build_summary_text(user_id: int, total_items: int) -> str:
    async for session in get_db():
        categories_stmt = (
            select(func.count(func.distinct(Product.category)))
            .select_from(Product)
            .join(Receipt)
            .where(Receipt.user_id == user_id)
        )
        category_count = await session.scalar(categories_stmt) or 0

        latest_stmt = (
            select(Product)
            .join(Receipt)
            .where(Receipt.user_id == user_id)
            .order_by(Product.id.desc())
            .limit(3)
        )
        latest_products = (await session.execute(latest_stmt)).scalars().all()

    latest_text = "\n".join(
        f"▫️ {product.name} — {product.quantity} шт"
        for product in latest_products
    ) or "▫️ Пока без новых поступлений"

    return (
        "🧊 <b>Твой Холодильник</b>\n\n"
        f"📦 Продуктов: <b>{total_items}</b>\n"
        f"🏷️ Категорий: <b>{category_count}</b>\n"
        "🆕 Последние добавления:\n"
        f"{latest_text}"
    )


async def _update_fridge_page(
    message_obj: types.Message,
    user_id: int,
    page: int,
    forced_total: int | None = None
):
    total_items = forced_total
    if total_items is None:
        total_items = await _get_total_products(user_id)
    if total_items == 0:
        await message_obj.edit_text("Холодильник пуст.")
        return

    total_pages = math.ceil(total_items / PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))

    async for session in get_db():
        stmt = (
            select(Product)
            .join(Receipt)
            .where(Receipt.user_id == user_id)
            .order_by(Product.id.desc())
            .offset(page * PAGE_SIZE)
            .limit(PAGE_SIZE)
        )
        products = (await session.execute(stmt)).scalars().all()

    if not products:
        await message_obj.edit_text("Не удалось загрузить продукты. Попробуй позже.")
        return

    lines = [
        f"📄 Страница {page + 1}/{total_pages}",
        ""
    ]
    for product in products:
        lines.append(
            f"▫️ <b>{product.name}</b>\n"
            f"   {product.quantity} шт · {product.price}₽ · {product.category or 'Без категории'}\n"
            f"   🔥 {product.calories}ккал | 🥩 {product.protein}г | 🥑 {product.fat}г | 🍞 {product.carbs}г"
        )
    text = "\n".join(lines)

    builder = InlineKeyboardBuilder()
    # Add eat buttons for each product
    for product in products:
        builder.button(text=f"🍽️ {product.name[:15]}", callback_data=f"eat_{product.id}")
    builder.adjust(2)  # 2 buttons per row
    
    # Navigation buttons
    if page > 0:
        builder.button(text="⬅️ Назад", callback_data=f"fridge_page:{page - 1}")
    if page < total_pages - 1:
        builder.button(text="Вперёд ➡️", callback_data=f"fridge_page:{page + 1}")
    builder.button(text="📄 Экспорт", callback_data="fridge_export")
    builder.adjust(2)

    await message_obj.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
