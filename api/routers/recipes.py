"""Recipes router for FoodFlow API."""
from fastapi import APIRouter
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

    # Generate via AI
    recipes = await AIService.generate_recipes(ingredients, request.category, settings)

    # Store in cache
    if recipes:
        await store_recipes(user.id, ingredients_hash, request.category, recipes)

    return [
        RecipeRead(
            title=r.get("title", "Без названия"),
            description=r.get("description"),
            calories=r.get("calories"),
            ingredients=r.get("ingredients", []),
            steps=r.get("steps", []),
        )
        for r in recipes
    ]
