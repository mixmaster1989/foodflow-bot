"""Module for recipe generation and display handlers.

Contains handlers for:
- Recipe category selection
- Recipe generation based on available ingredients
- Recipe caching and display
"""
from datetime import datetime

from aiogram import F, Router, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.future import select

from database.base import get_db
from database.models import Product, Receipt
from services.ai import AIService
from services.cache import get_cached_recipes, make_hash, store_recipes
from services.logger import log_error, log_request, log_response

router = Router()

# Telegram message limit is 4096 characters
MAX_MESSAGE_LENGTH: int = 4096


def split_long_message(text: str, max_length: int = MAX_MESSAGE_LENGTH) -> list[str]:
    """Split long message into chunks that fit Telegram limit.

    Args:
        text: Message text to split
        max_length: Maximum length per chunk (default: 4096)

    Returns:
        List of message chunks

    """
    if len(text) <= max_length:
        return [text]

    chunks = []
    current_chunk = ""

    for line in text.split('\n'):
        # If adding this line would exceed limit, save current chunk and start new
        if len(current_chunk) + len(line) + 1 > max_length:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = line + '\n'
        else:
            current_chunk += line + '\n'

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks

# --- Level 3.1: Categories ---
@router.callback_query(F.data == "menu_recipes")
async def show_recipe_categories(callback: types.CallbackQuery) -> None:
    """Show recipe category selection menu.

    Args:
        callback: Telegram callback query

    """
    builder = InlineKeyboardBuilder()
    builder.button(text="🥗 Салаты", callback_data="recipes_cat:Salads")
    builder.button(text="🥘 Горячее", callback_data="recipes_cat:Main")
    builder.button(text="🍰 Десерты", callback_data="recipes_cat:Dessert")
    builder.button(text="🍳 Завтраки", callback_data="recipes_cat:Breakfast")
    builder.button(text="🔙 Назад", callback_data="main_menu")
    builder.adjust(2, 2, 1)

    # Image path
    photo_path = types.FSInputFile("assets/recipes.png")

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
    
    from database.base import get_db
    from services.ai_guide import AIGuideService
    async for session in get_db():
        await AIGuideService.track_activity(callback.from_user.id, "recipes", session)
        break
        
    await callback.answer()

# --- Level 3.2: Generate & List ---
@router.callback_query(F.data.startswith("recipes_cat:"))
async def generate_recipes_by_category(callback: types.CallbackQuery) -> None:
    """Generate recipes for selected category or show cached results.

    Args:
        callback: Telegram callback query with data format "recipes_cat:Category" or "recipes_cat:Category:refresh"

    """
    # Answer callback IMMEDIATELY to prevent timeout on long AI operations
    await callback.answer()

    # callback data can be 'recipes_cat:Category' or 'recipes_cat:Category:refresh'
    parts = callback.data.split(":")
    category = parts[1]
    refresh_requested = len(parts) > 2 and parts[2] == "refresh"

    # Edit photo message with status, keep the image
    photo_path = types.FSInputFile("assets/recipes.png")
    status_caption = f"👨‍🍳 Думаю над рецептами ({category})..."

    try:
        status_msg = await callback.message.edit_media(
            media=types.InputMediaPhoto(media=photo_path, caption=status_caption, parse_mode="HTML")
        )
    except Exception:
        # If edit fails, send new photo
        status_msg = await callback.message.answer_photo(
            photo=photo_path,
            caption=status_caption,
            parse_mode="HTML"
        )

    # 1. Get ingredients
    ingredients = []
    async for session in get_db():
        stmt = (
            select(Product)
            .outerjoin(Receipt)
            .where(
                (Receipt.user_id == callback.from_user.id)
                | (Product.user_id == callback.from_user.id)
            )
        )
        result = await session.execute(stmt)
        products = result.scalars().all()
        ingredients = [p.name for p in products]

        # Get user settings
        from database.models import UserSettings
        settings_stmt = select(UserSettings).where(UserSettings.user_id == callback.from_user.id)
        settings_res = await session.execute(settings_stmt)
        user_settings = settings_res.scalar_one_or_none()

    # Log request details
    log_request(callback.from_user.id, ingredients, category, f"Requesting recipes for category {category}")

    if not ingredients:
        builder = InlineKeyboardBuilder()
        builder.button(text="🔙 Назад", callback_data="menu_recipes")
        try:
            await status_msg.edit_media(
                media=types.InputMediaPhoto(media=photo_path, caption="В холодильнике пусто! 🕸️\nСкинь чек, чтобы я мог предложить рецепты.", parse_mode="HTML"),
                reply_markup=builder.as_markup()
            )
        except Exception:
            await status_msg.edit_text(
                "В холодильнике пусто! 🕸️\nСкинь чек, чтобы я мог предложить рецепты.",
                reply_markup=builder.as_markup()
            )
        return

    # Compute hash of ingredients for caching
    ingredients_hash = make_hash(ingredients)
    # Try to fetch from cache if not a refresh request
    cached = []
    if not refresh_requested:
        cached = await get_cached_recipes(callback.from_user.id, ingredients_hash, category)
        # Filter recent entries (younger than 5 minutes)
        recent = [c for c in cached if (datetime.now() - c.created_at).total_seconds() < 300]
        if recent:
            # Build response from cached recipes
            response_text = f"👨‍🍳 <b>Рецепты: {category}</b>\n\n"
            for i, rec in enumerate(recent, 1):
                response_text += f"{i}. <b>{rec.title}</b> (~{rec.calories if rec.calories else '?'} ккал)\n"
                response_text += f"   <i>{rec.description}</i>\n"
                if rec.ingredients:
                    response_text += "   <u>Ингредиенты:</u>\n"
                    for ing in rec.ingredients:
                        response_text += f"     • {ing.get('name')}: {ing.get('amount')}\n"
                if rec.steps:
                    response_text += "   <u>Приготовление:</u>\n"
                    for idx, step in enumerate(rec.steps, 1):
                        response_text += f"     {idx}. {step}\n"
                response_text += "\n"

            # Split message if too long
            message_chunks = split_long_message(response_text)

            # Add refresh and back buttons
            builder = InlineKeyboardBuilder()
            builder.button(text="🔄 Другие варианты", callback_data=f"recipes_cat:{category}:refresh")
            builder.button(text="🔙 Назад", callback_data="menu_recipes")

            # Update photo with short caption, send recipes as separate messages
            short_caption = f"👨‍🍳 <b>Рецепты: {category}</b>\n\nНайдено {len(recent)} рецептов из кеша!"
            try:
                await status_msg.edit_media(
                    media=types.InputMediaPhoto(media=photo_path, caption=short_caption, parse_mode="HTML"),
                    reply_markup=builder.as_markup()
                )
            except Exception:
                await status_msg.edit_text(short_caption, reply_markup=builder.as_markup(), parse_mode="HTML")

            # Send recipe chunks as separate messages
            if message_chunks:
                for chunk in message_chunks:
                    await callback.message.answer(chunk, parse_mode="HTML")
            log_response(callback.from_user.id, {"cached": True, "count": len(recent)}, True)
            return

    # If we reach here, we need to call AI (no cache or refresh requested)
    
    # 2. Check Daily Refresh Limit (3 per day)
    from datetime import date
    today_str = date.today().isoformat()
    
    if refresh_requested:
        async for session in get_db():
            if not user_settings:
                from database.models import UserSettings
                user_settings = UserSettings(user_id=callback.from_user.id)
                session.add(user_settings)
            
            if user_settings.last_recipe_refresh_date == today_str:
                if user_settings.recipe_refresh_count >= 3:
                    builder = InlineKeyboardBuilder()
                    builder.button(text="🔙 Назад", callback_data="menu_recipes")
                    limit_text = "⚠️ <b>Лимит обновлений исчерпан!</b>\n\nВы можете обновлять рецепты не более 3 раз в день. Попробуйте завтра или используйте текущий список."
                    try:
                        await status_msg.edit_media(
                            media=types.InputMediaPhoto(media=photo_path, caption=limit_text, parse_mode="HTML"),
                            reply_markup=builder.as_markup()
                        )
                    except Exception:
                        await status_msg.edit_text(limit_text, reply_markup=builder.as_markup(), parse_mode="HTML")
                    return
                user_settings.recipe_refresh_count += 1
            else:
                user_settings.last_recipe_refresh_date = today_str
                user_settings.recipe_refresh_count = 1
            
            await session.commit()

    # 3. Call AI with category to get appropriate recipes
    try:
        data = await AIService.generate_recipes(ingredients, category, user_settings)

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
            response_text += f"{i}. <b>{recipe['title']}</b> (~{recipe.get('calories', '?')} ккал)\n"
            response_text += f"   <i>{recipe.get('description', '')}</i>\n"
            # Ingredients list
            ingredients = recipe.get('ingredients')
            if ingredients:
                response_text += "   <u>Ингредиенты:</u>\n"
                for ing in ingredients:
                    name = ing.get('name', '')
                    amount = ing.get('amount', '')
                    response_text += f"     • {name}: {amount}\n"
            # Steps list
            steps = recipe.get('steps')
            if steps:
                response_text += "   <u>Приготовление:</u>\n"
                for idx, step in enumerate(steps, 1):
                    response_text += f"     {idx}. {step}\n"
            response_text += "\n"

        # Save recipes to cache
        await store_recipes(callback.from_user.id, ingredients_hash, category, data["recipes"])

        # Split message if too long
        message_chunks = split_long_message(response_text)

        builder = InlineKeyboardBuilder()
        builder.button(text="🔄 Другие варианты", callback_data=f"recipes_cat:{category}:refresh")
        builder.button(text="🔙 Назад", callback_data="menu_recipes")

        # Update photo with short caption, send recipes as separate messages
        short_caption = f"👨‍🍳 <b>Рецепты: {category}</b>\n\nСгенерировано {len(data['recipes'])} рецептов!"
        try:
            await status_msg.edit_media(
                media=types.InputMediaPhoto(media=photo_path, caption=short_caption, parse_mode="HTML"),
                reply_markup=builder.as_markup()
            )
        except Exception:
            await status_msg.edit_text(short_caption, reply_markup=builder.as_markup(), parse_mode="HTML")

        # Send recipe chunks as separate messages
        if message_chunks:
            for chunk in message_chunks:
                await callback.message.answer(chunk, parse_mode="HTML")

        log_response(callback.from_user.id, {"cached": False, "count": len(data["recipes"])}, False)

    except Exception as e:
        log_error(callback.from_user.id, e)
        builder = InlineKeyboardBuilder()
        builder.button(text="🔙 Назад", callback_data="menu_recipes")
        error_caption = f"❌ Ошибка шеф-повара: {e}"
        try:
            await status_msg.edit_media(
                media=types.InputMediaPhoto(media=photo_path, caption=error_caption, parse_mode="HTML"),
                reply_markup=builder.as_markup()
            )
        except Exception:
            await status_msg.edit_text(error_caption, reply_markup=builder.as_markup())
