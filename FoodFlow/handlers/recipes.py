from aiogram import Router, F, types
from sqlalchemy.future import select
from FoodFlow.database.base import get_db
from FoodFlow.database.models import Product, Receipt
from FoodFlow.services.ai import AIService

router = Router()

@router.message(F.text == "👨‍🍳 Рецепты")
async def show_recipes(message: types.Message):
    status_msg = await message.answer("👨‍🍳 **Шеф думает...**\n\nСмотрю в холодильник и подбираю варианты...")
    
    # 1. Get ingredients
    ingredients = []
    async for session in get_db():
        stmt = select(Product).join(Receipt).where(Receipt.user_id == message.from_user.id)
        result = await session.execute(stmt)
        products = result.scalars().all()
        ingredients = [p.name for p in products]
        
    if not ingredients:
        await status_msg.edit_text("В холодильнике пусто! 🕸️\nСкинь чек, чтобы я мог предложить рецепты.")
        return
        
    # 2. Call AI
    try:
        data = await AIService.generate_recipes(ingredients)
        
        if not data or "recipes" not in data:
            await status_msg.edit_text("Не смог придумать рецепты... Попробуй позже.")
            return
            
        # 3. Format response
        response_text = "👨‍🍳 **Вот что можно приготовить:**\n\n"
        for i, recipe in enumerate(data["recipes"], 1):
            response_text += (
                f"{i}. **{recipe['title']}** (~{recipe.get('calories', '?')} ккал)\n"
                f"   _{recipe['description']}_\n\n"
            )
            
        await status_msg.edit_text(response_text, parse_mode="Markdown")
        
    except Exception as e:
        await status_msg.edit_text(f"Ошибка шеф-повара: {e}")
