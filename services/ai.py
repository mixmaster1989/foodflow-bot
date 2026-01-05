"""Module for AI-powered recipe generation.

Contains:
- AIService: Generates recipes based on available ingredients and category
"""
import json
import logging
from typing import Any

import aiohttp

from config import settings

logger = logging.getLogger(__name__)


class AIService:
    """Generate recipes using AI models based on available ingredients.

    Supports multiple recipe categories (Salads, Main, Dessert, Breakfast)
    and uses fallback models for reliability.

    Attributes:
        MODELS: List of fallback models ordered by quality (best first)

    Example:
        >>> service = AIService()
        >>> recipes = await service.generate_recipes(['Молоко', 'Яйца'], 'Breakfast')
        >>> print(recipes['recipes'][0]['title'])
        'Омлет с молоком'

    """

    MODELS: list[str] = [
        "openai/gpt-oss-120b:medium",  # User‑selected higher‑capacity model
        "mistralai/mistral-small-3.2-24b-instruct:free", # Working & Smart
        "qwen/qwen3-30b-a3b:free",                        # Working & New
        "google/gemma-3-27b-it:free",                     # Good but unstable
        "deepseek/deepseek-chat-v3-0324:free",            # Good but unstable
        "openai/gpt-oss-20b:free"                         # Working fallback
    ]

    @classmethod
    async def generate_recipes(cls, ingredients: list[str], category: str, user_settings: Any = None) -> dict[str, Any] | None:
        """Generate recipes based on available ingredients and category.

        Args:
            ingredients: List of available ingredient names
            category: Recipe category (Salads, Main, Dessert, Breakfast)
            user_settings: User settings model (optional)

        Returns:
            Dictionary with 'recipes' key containing list of recipe dicts, or None.

        """
        if not ingredients:
            return None

        ingredients_str = ", ".join(ingredients)

        context_str = ""
        if user_settings:
            goal_map = {
                "lose_weight": "похудение (низкокалорийные)",
                "maintain": "поддержание веса (сбалансированные)",
                "gain_mass": "набор массы (высокобелковые)",
                "healthy": "здоровое питание"
            }
            goal_text = goal_map.get(user_settings.goal, "здоровое питание")
            allergies = user_settings.allergies if user_settings.allergies else "нет"
            
            context_str = (
                f"USER PROFILE:\n"
                f"- Goal: {goal_text}\n"
                f"- Allergies/Restrictions: {allergies}\n"
                f"IMPORTANT: Adjust recipes to fit this goal. If goal is weight loss, minimize fat/sugar. If allergies exist, EXCLUDE those ingredients.\n"
            )

        prompt = (
            f"I have these ingredients: {ingredients_str}. "
            f"Suggest 3 simple {category.lower()} recipes using mostly these ingredients. "
            f"{context_str}"
            "For each recipe, provide a title, a short description, estimated calories per serving, a list of ingredients with quantities, and step‑by‑step preparation instructions. "
            "Respond ONLY in Russian language. "
            "Return ONLY a JSON object with this format: "
            "{\"recipes\": [{\"title\": \"...\", \"description\": \"...\", \"calories\": 500, \"ingredients\": [{\"name\": \"...\", \"amount\": \"...\"}], \"steps\": [\"...\"]}]}"
        )

        for model in cls.MODELS:
            result = await cls._call_model(model, prompt)
            if result:
                return result

        return None

    @staticmethod
    async def _call_model(model: str, prompt: str) -> dict[str, Any] | None:
        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://foodflow.app",
            "X-Title": "FoodFlow Bot"
        }

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }

        import asyncio

        # Retry logic: 3 attempts with 0.5s delay
        for attempt in range(3):
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers=headers,
                        json=payload,
                        timeout=45
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            content = result['choices'][0]['message']['content']
                            # Clean markdown
                            content = content.replace("```json", "").replace("```", "").strip()
                            return json.loads(content)
                        else:
                            logger.warning(f"AI Recipe ({model}) attempt {attempt+1}/3 failed: {response.status}")
                            if attempt < 2:
                                await asyncio.sleep(0.5)
                                continue
                except Exception as e:
                    logger.error(f"Exception in AI Service ({model}) attempt {attempt+1}/3: {e}")
                    if attempt < 2:
                        await asyncio.sleep(0.5)
                        continue
        return None
