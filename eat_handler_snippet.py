# Add eat handler to fridge.py
from database.models import ConsumptionLog
from datetime import datetime

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
        break
    
    await callback.answer(f"✅ Съел {product.name}!")
    # Refresh page
    total = await _get_total_products(callback.from_user.id)
    await _update_fridge_page(callback.message, callback.from_user.id, page=0, forced_total=total)
