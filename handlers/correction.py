from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.base import get_db
from database.models import Product
from sqlalchemy import select

router = Router()

class CorrectionStates(StatesGroup):
    waiting_for_correction = State()

@router.callback_query(F.data.startswith("correct_"))
async def start_correction(callback: types.CallbackQuery, state: FSMContext):
    """Handle correction button click - pre-fill current name for editing"""
    product_id = int(callback.data.split("_")[1])
    
    # Get current product name from DB
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
        await state.set_state(CorrectionStates.waiting_for_correction)
        
        # Send message with current name (user will edit and send back)
        await callback.message.answer(
            f"✏️ <b>Текущее название:</b>\n<code>{product.name}</code>\n\n"
            f"Отправьте исправленное название:",
            parse_mode="HTML"
        )
        await callback.answer()

@router.message(CorrectionStates.waiting_for_correction)
async def apply_correction(message: types.Message, state: FSMContext):
    """Apply user's correction to the product"""
    data = await state.get_data()
    product_id = data.get("product_id")
    new_name = message.text.strip()
    
    if not new_name:
        await message.answer("❌ Название не может быть пустым")
        return
    
    # Update product in DB
    async for session in get_db():
        result = await session.execute(
            select(Product).where(Product.id == product_id)
        )
        product = result.scalar_one_or_none()
        
        if product:
            old_name = product.name
            product.name = new_name
            await session.commit()
            
            # Send updated product card
            builder = InlineKeyboardBuilder()
            builder.button(text="✏️ Коррекция", callback_data=f"correct_{product_id}")
            
            await message.answer(
                f"✅ <b>Обновлено!</b>\n\n"
                f"▫️ <b>{product.name}</b>\n"
                f"💵 {product.price}р × {product.quantity} шт\n"
                f"🏷️ {product.category}",
                reply_markup=builder.as_markup(),
                parse_mode="HTML"
            )
        else:
            await message.answer("❌ Продукт не найден")
    
    await state.clear()
