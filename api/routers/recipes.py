"""Recipes router for FoodFlow API."""
import pytz
from datetime import datetime
from fastapi import APIRouter, HTTPException
from sqlalchemy import or_, select

from api.auth import CurrentUser, DBSession
from api.schemas import RecipeRead, RecipeRequest
from database.models import Product, UserSettings
from services.ai import AIService
from services.cache import get_cached_recipes, make_hash, store_recipes

router = APIRouter()


CATEGORIES = [
    "🍳 Завтрак",
    "🥗 Обед",
    "🍝 Ужин",
    "🥤 Перекус",
    "🍰 Десерт",
]


@router.get("/categories")
async def list_categories():
    """List available recipe categories."""
    return {"categories": CATEGORIES}


@router.post("/generate", response_model=list[RecipeRead])
async def generate_recipes(
    request: RecipeRequest,
    user: CurrentUser,
    session: DBSession,
):
    """Generate recipes based on available ingredients."""
    # Get user's products
    stmt = (
        select(Product)
        .where(or_(Product.user_id == user.id))
        .order_by(Product.id.desc())
        .limit(50)
    )
    products = (await session.execute(stmt)).scalars().all()
    ingredients = [p.name for p in products]

    if not ingredients:
        ingredients = ["яйца", "молоко", "хлеб"]  # Defaults

    # Check cache
    ingredients_hash = make_hash(ingredients)
    if not request.refresh:
        cached = await get_cached_recipes(user.id, ingredients_hash, request.category)
        if cached:
            return cached

    # Get user settings
    settings_stmt = select(UserSettings).where(UserSettings.user_id == user.id)
    settings = (await session.execute(settings_stmt)).scalar_one_or_none()

    if not settings:
        settings = UserSettings(user_id=user.id)
        session.add(settings)

    # === Daily Refresh Limit Check (3 per day) ===
    msk_tz = pytz.timezone("Europe/Moscow")
    today_str = datetime.now(msk_tz).date().isoformat()

    if request.refresh:
        if settings.last_recipe_refresh_date == today_str:
            if settings.recipe_refresh_count >= 3:
                raise HTTPException(
                    status_code=429,
                    detail="Лимит обновлений (3 в день) исчерпан. Попробуйте завтра!"
                )
        # Don't commit the debit until we know the AI succeeded

    # Generate via AI
    ai_response = await AIService.generate_recipes(ingredients, request.category, settings)
    recipes = ai_response.get("recipes", []) if ai_response else []

    if request.refresh:
        if not recipes:
            raise HTTPException(status_code=503, detail="AI временно недоступен, попробуйте ещё раз")
        if settings.last_recipe_refresh_date == today_str:
            settings.recipe_refresh_count += 1
        else:
            settings.last_recipe_refresh_date = today_str
            settings.recipe_refresh_count = 1
        await session.commit()

    # Store in cache
    if recipes:
        await store_recipes(user.id, ingredients_hash, request.category, recipes)

    return [
        RecipeRead(
            title=r.get("title", "Без названия"),
            description=r.get("description", ""),
            calories=r.get("calories", 0),
            ingredients=r.get("ingredients", []),
            steps=r.get("steps", []),
        )
        for r in recipes
    ]
