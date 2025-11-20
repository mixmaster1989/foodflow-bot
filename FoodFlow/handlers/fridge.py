from aiogram import Router, F, types
from sqlalchemy.future import select
from FoodFlow.database.base import get_db
from FoodFlow.database.models import Product

router = Router()

@router.message(F.text == "🧊 Холодильник")
async def show_fridge(message: types.Message):
    async for session in get_db():
        # Join with Receipt to filter by user if needed, but Product doesn't have user_id directly.
        # We need to join Product -> Receipt -> User
        # For MVP, let's assume we just show all products for the user's receipts.
        # Wait, Product -> Receipt. Receipt -> User.
        
        # Correct query: Select Product where Product.receipt.user_id == message.from_user.id
        # But for simplicity in MVP let's just assume we fetch all products linked to receipts of this user.
        # Actually, let's do it properly.
        pass 
        # (I will implement the query logic inside the loop below to be safe with imports)

    # Re-implementing with correct query
    from FoodFlow.database.models import Receipt
    
    items_text = "🧊 **Твой Холодильник:**\n\n"
    has_items = False
    
    async for session in get_db():
        stmt = select(Product).join(Receipt).where(Receipt.user_id == message.from_user.id)
        result = await session.execute(stmt)
        products = result.scalars().all()
        
        if not products:
            await message.answer("В холодильнике пусто! 🕸️\nСкинь фото чека, чтобы пополнить запасы.")
            return

        # Group by category (simple logic for now)
        for product in products:
            items_text += f"▫️ {product.name} ({product.quantity} шт)\n"
            has_items = True
            
    if has_items:
        await message.answer(items_text)
