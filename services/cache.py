"""Module for caching recipe generation results.

Contains utility functions for:
- Creating deterministic hashes from ingredient lists
- Checking cache entry freshness
- Retrieving and storing cached recipes
"""
import hashlib
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.future import select

from database.base import async_session
from database.models import CachedRecipe


def make_hash(ingredients: list[str]) -> str:
    """Create a deterministic SHA256 hash of a sorted ingredient list.

    Args:
        ingredients: List of ingredient names

    Returns:
        Hexadecimal SHA256 hash string

    Example:
        >>> hash1 = make_hash(['Молоко', 'Яйца'])
        >>> hash2 = make_hash(['Яйца', 'Молоко'])  # Same hash (sorted)
        >>> assert hash1 == hash2

    """
    sorted_ing = sorted([ing.strip().lower() for ing in ingredients])
    joined = "|".join(sorted_ing)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def is_recent(entry: CachedRecipe, minutes: int = 5) -> bool:
    """Check if a cached entry is younger than specified minutes.

    Args:
        entry: CachedRecipe database entry
        minutes: Maximum age in minutes (default: 5)

    Returns:
        True if entry is younger than specified minutes, False otherwise

    """
    return datetime.utcnow() - entry.created_at < timedelta(minutes=minutes)


async def get_cached_recipes(user_id: int, ingredients_hash: str, category: str) -> list[CachedRecipe]:
    """Retrieve cached recipes for given user, ingredients hash, and category.

    Args:
        user_id: Telegram user ID
        ingredients_hash: SHA256 hash of sorted ingredient list
        category: Recipe category (Salads, Main, Dessert, Breakfast)

    Returns:
        List of CachedRecipe objects matching the criteria

    """
    async with async_session() as session:
        stmt = select(CachedRecipe).where(
            CachedRecipe.user_id == user_id,
            CachedRecipe.ingredients_hash == ingredients_hash,
            CachedRecipe.category == category,
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def store_recipes(user_id: int, ingredients_hash: str, category: str, recipes: list[dict[str, Any]]) -> None:
    """Store generated recipes in cache for future retrieval.

    Args:
        user_id: Telegram user ID
        ingredients_hash: SHA256 hash of sorted ingredient list
        category: Recipe category (Salads, Main, Dessert, Breakfast)
        recipes: List of recipe dictionaries with 'title', 'description', 'calories',
                 'ingredients', 'steps' keys

    Returns:
        None

    """
    async with async_session() as session:
        for rec in recipes:
            cached = CachedRecipe(
                user_id=user_id,
                ingredients_hash=ingredients_hash,
                category=category,
                title=rec.get("title", ""),
                description=rec.get("description", ""),
                calories=rec.get("calories"),
                ingredients=rec.get("ingredients", []),
                steps=rec.get("steps", []),
            )
            session.add(cached)
        await session.commit()
