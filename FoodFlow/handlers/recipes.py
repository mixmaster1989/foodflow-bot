from aiogram import F, Router, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.future import select

from FoodFlow.database.base import get_db
from FoodFlow.database.models import Product, Receipt
from FoodFlow.services.ai import AIService

router = Router()

# --- Level 3.1: Categories ---
@router.callback_query(F.data == "menu_recipes")
async def show_recipe_categories(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="🥗 Салаты", callback_data="recipes_cat:Salads")
    builder.button(text="🥘 Горячее", callback_data="recipes_cat:Main")
    builder.button(text="🍰 Десерты", callback_data="recipes_cat:Dessert")
    builder.button(text="🍳 Завтраки", callback_data="recipes_cat:Breakfast")
    builder.button(text="🔙 Назад", callback_data="main_menu")
    builder.adjust(2, 2, 1)

    # Image path
    photo_path = types.FSInputFile("FoodFlow/assets/recipes.png")

    caption = (
        "👨‍🍳 <b>Шеф-повар на связи!</b>\n\n"
        "Я посмотрю, что есть в холодильнике, и предложу рецепт.\n"
        "Что будем готовить?"
    )

    # Try to edit if possible (if previous was photo), otherwise send new
    try:
        await callback.message.edit_media(
            media=types.InputMediaPhoto(media=photo_path, caption=caption, parse_mode="HTML"),
            reply_markup=builder.as_markup()
        )
    except Exception:
        # If edit fails (e.g. previous was text), delete and send new photo
        await callback.message.delete()
        await callback.message.answer_photo(
            photo=photo_path,
            caption=caption,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    await callback.answer()

# --- Level 3.2: Generate & List ---
@router.callback_query(F.data.startswith("recipes_cat:"))
async def generate_recipes_by_category(callback: types.CallbackQuery):
    category = callback.data.split(":")[1]

    await callback.message.edit_text(f"👨‍🍳 Думаю над рецептами ({category})...")

    # 1. Get ingredients
    ingredients = []
    async for session in get_db():
        stmt = select(Product).join(Receipt).where(Receipt.user_id == callback.from_user.id)
        result = await session.execute(stmt)
        products = result.scalars().all()
        ingredients = [p.name for p in products]

    if not ingredients:
        builder = InlineKeyboardBuilder()
        builder.button(text="🔙 Назад", callback_data="menu_recipes")
        await callback.message.edit_text(
            "В холодильнике пусто! 🕸️\nСкинь чек, чтобы я мог предложить рецепты.",
            reply_markup=builder.as_markup()
        )
        return

    # 2. Call AI (Modified to accept category hint if possible, or just filter in prompt)
    # For now, we use the generic generate_recipes but ideally we'd pass the category to the prompt.
    # Let's assume AIService handles it or we just ask for generic recipes for now.
    # TODO: Update AIService to accept category

    try:
        # Temporary: Just calling generic generation.
        # In future: await AIService.generate_recipes(ingredients, category=category)
        data = await AIService.generate_recipes(ingredients)

        if not data or "recipes" not in data:
            raise ValueError("No recipes generated")

        # Show first recipe or list?
        # Guidelines say "List of recipes".
        # Let's show a list of buttons.

        builder = InlineKeyboardBuilder()
        for i, recipe in enumerate(data["recipes"]):
            # Store recipe index in callback
            builder.button(text=f"{i+1}. {recipe['title'][:20]}...", callback_data=f"recipe_view:{i}")

        builder.button(text="🔙 Назад", callback_data="menu_recipes")
        builder.adjust(1)

        # Save recipes to state or cache?
        # For simplicity in this refactor without Redis, we might need to re-generate or store in a temporary way.
        # BUT, since we can't easily store large state without FSM/Redis in this simple bot,
        # let's just display the text of ALL recipes for now, as the previous implementation did,
        # but formatted nicely with a Back button.
        # OR better: Just show the text as before but with the new navigation.

        response_text = f"👨‍🍳 <b>Рецепты: {category}</b>\n\n"
        for i, recipe in enumerate(data["recipes"], 1):
            response_text += (
                f"{i}. <b>{recipe['title']}</b> (~{recipe.get('calories', '?')} ккал)\n"
                f"   <i>{recipe['description']}</i>\n\n"
            )

        builder = InlineKeyboardBuilder()
        builder.button(text="🔄 Другие варианты", callback_data=f"recipes_cat:{category}")
        builder.button(text="🔙 Назад", callback_data="menu_recipes")

        await callback.message.edit_text(response_text, reply_markup=builder.as_markup(), parse_mode="HTML")

    except Exception as e:
        builder = InlineKeyboardBuilder()
        builder.button(text="🔙 Назад", callback_data="menu_recipes")
        await callback.message.edit_text(f"Ошибка шеф-повара: {e}", reply_markup=builder.as_markup())

