import hashlib
import json
from datetime import datetime, timedelta
from typing import List, Dict
from sqlalchemy.future import select
from database.base import async_session
from database.models import CachedRecipe


def make_hash(ingredients: List[str]) -> str:
    """Create a deterministic SHA256 hash of a sorted ingredient list."""
    sorted_ing = sorted([ing.strip().lower() for ing in ingredients])
    joined = "|".join(sorted_ing)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def is_recent(entry: CachedRecipe, minutes: int = 5) -> bool:
    """Check if a cached entry is younger than *minutes* minutes."""
    return datetime.utcnow() - entry.created_at < timedelta(minutes=minutes)


async def get_cached_recipes(user_id: int, ingredients_hash: str, category: str) -> List[CachedRecipe]:
    async with async_session() as session:
        stmt = select(CachedRecipe).where(
            CachedRecipe.user_id == user_id,
            CachedRecipe.ingredients_hash == ingredients_hash,
            CachedRecipe.category == category,
        )
        result = await session.execute(stmt)
        return result.scalars().all()


async def store_recipes(user_id: int, ingredients_hash: str, category: str, recipes: List[Dict]):
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
