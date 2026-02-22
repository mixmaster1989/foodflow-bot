"""Module for AI-powered product consultation service.

Contains:
- ConsultantService: Analyzes products based on user profile and provides recommendations
"""
import json
import logging
from typing import Any

from database.models import Product, UserSettings
from services.ai import AIService

logger = logging.getLogger(__name__)


class ConsultantService:
    """Service for analyzing products and providing personalized recommendations.

    Uses AI to generate smart, personalized recommendations based on user profile
    (gender, height, weight, goal) and product data.

    Attributes:
        MODELS: List of AI models for consultation (same as AIService)

    Example:
        >>> service = ConsultantService()
        >>> product = Product(name="Шоколад", calories=500, category="Сладости")
        >>> user_settings = UserSettings(gender="male", height=180, weight=80, goal="lose_weight")
        >>> result = await service.analyze_product(product, user_settings)
        >>> print(result['warnings'])
        ['⚠️ Высокая калорийность для похудения']
    """

    MODELS: list[str] = AIService.MODELS

    @classmethod
    async def analyze_product(
        cls,
        product: Product,
        user_settings: UserSettings,
        context: str = "general",
        fridge_snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Analyze a single product and provide recommendations.

        Args:
            product: Product to analyze
            user_settings: User profile with goals and preferences
            context: Context where product is used ("receipt", "fridge", "shopping_list", "shopping")

        Returns:
            Dictionary with keys:
            - warnings: List of warning messages
            - recommendations: List of positive recommendations
            - missing: List of suggestions for missing items

        """
        # If user hasn't completed onboarding, return empty recommendations
        if not user_settings.is_initialized:
            return {"warnings": [], "recommendations": [], "missing": []}

        try:
            result = await cls._generate_ai_recommendation(
                product, user_settings, context, fridge_snapshot
            )
            if result:
                return result
        except Exception as e:
            logger.error(f"AI consultation failed: {e}, falling back to simple rules")
            # Fallback to simple rules if AI fails
            return cls._calculate_simple_recommendations(product, user_settings)

        return {"warnings": [], "recommendations": [], "missing": []}

    @classmethod
    async def analyze_products(
        cls, products: list[Product], user_settings: UserSettings, context: str = "receipt"
    ) -> dict[str, Any]:
        """Analyze multiple products and provide aggregate recommendations.

        Args:
            products: List of products to analyze
            user_settings: User profile with goals and preferences
            context: Context where products are used

        Returns:
            Dictionary with aggregate warnings, recommendations, and missing items

        """
        if not user_settings.is_initialized or not products:
            return {"warnings": [], "recommendations": [], "missing": []}

        # Analyze all products
        all_warnings: list[str] = []
        all_recommendations: list[str] = []
        all_missing: list[str] = []

        for product in products:
            result = await cls.analyze_product(product, user_settings, context)
            all_warnings.extend(result.get("warnings", []))
            all_recommendations.extend(result.get("recommendations", []))
            all_missing.extend(result.get("missing", []))

        # Remove duplicates while preserving order
        unique_warnings = list(dict.fromkeys(all_warnings))
        unique_recommendations = list(dict.fromkeys(all_recommendations))
        unique_missing = list(dict.fromkeys(all_missing))

        return {
            "warnings": unique_warnings,
            "recommendations": unique_recommendations,
            "missing": unique_missing,
        }

    @classmethod
    async def _generate_ai_recommendation(
        cls,
        product: Product,
        user_settings: UserSettings,
        context: str,
        fridge_snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Generate AI-powered recommendation for a product.

        Args:
            product: Product to analyze
            user_settings: User profile
            context: Context of usage

        Returns:
            Dictionary with warnings, recommendations, missing, or None if AI fails

        """
        # Build user profile description
        gender_text = "мужской" if user_settings.gender == "male" else "женский"
        goal_text = {
            "lose_weight": "похудение / дефицит",
            "maintain": "не набирать / поддерживать вес",
            "healthy": "здоровое питание / баланс",
            "gain_mass": "набрать массу",
        }.get(user_settings.goal, "здоровое питание")

        context_text = {
            "receipt": "чек из магазина",
            "fridge": "холодильник",
            "shopping_list": "список покупок",
            "shopping": "режим покупок",
            "general": "общий контекст",
        }.get(context, "общий контекст")

        # Build product description
        product_info = (
            f"Название: {product.name}\n"
            f"Категория: {product.category or 'Не указана'}\n"
            f"Калории: {product.calories:.0f} ккал\n"
            f"Белки: {product.protein:.1f} г\n"
            f"Жиры: {product.fat:.1f} г\n"
            f"Углеводы: {product.carbs:.1f} г"
        )

        allergies_text = (
            f"Аллергии/исключения: {user_settings.allergies}"
            if user_settings.allergies
            else "Аллергий нет"
        )

        snapshot_text = ""
        if fridge_snapshot:
            total = fridge_snapshot.get("totals", {})
            items = fridge_snapshot.get("items", [])
            snapshot_text = (
                "\n📊 <b>В холодильнике:</b>\n"
                f"<blockquote>- Продуктов: <code>{len(items)}</code>\n"
                + ("\n".join(f"• {i}" for i in items) if items else "• Нет данных") + "</blockquote>"
                "\n🍱 <b>Итого КБЖУ:</b>\n"
                f"<blockquote>🔥 <code>{total.get('calories', 0):.0f}</code> | 🥩 <code>{total.get('protein', 0):.1f}</code> | 🥑 <code>{total.get('fat', 0):.1f}</code> | 🍞 <code>{total.get('carbs', 0):.1f}</code></blockquote>\n"
            )

        # Build prompt without escaping hell: double braces for literal JSON braces
        prompt = (
            "Ты - персональный консультант по питанию. Проанализируй продукт и дай рекомендации.\n\n"
            "<b>Профиль пользователя:</b>\n"
            f"- Пол: {gender_text}\n"
            f"- Рост: {user_settings.height} см\n"
            f"- Вес: {user_settings.weight} кг\n"
            f"- Цель: {goal_text}\n"
            f"- Дневная норма калорий: {user_settings.calorie_goal} ккал\n"
            f"- Дневная норма белков: {user_settings.protein_goal} г\n"
            f"- Дневная норма жиров: {user_settings.fat_goal} г\n"
            f"- Дневная норма углеводов: {user_settings.carb_goal} г\n"
            f"- {allergies_text}\n\n"
            f"<b>Продукт:</b>\n{product_info}\n\n"
            f"{snapshot_text + chr(10) if snapshot_text else ''}"
            f"<b>Контекст:</b> {context_text}\n\n"
            "Твоя задача: Дать КРАТКИЙ и ТОЧНЫЙ совет по МЕННО ЭТОМУ продукту.\n"
            "1. Не перечисляй содержимое холодильника, используй его только чтобы посоветовать с чем сочетать ЭТОТ продукт.\n"
            "2. Если КБЖУ продукта = 0 (ошибка данных), скажи об этом.\n"
            "3. Максимум 2-3 пункта советов.\n"
            "4. Не пиши общие фразы ('Питайтесь правильно').\n"
            "5. Обращайся к пользователю на 'ты'."
            "Если продукт полезен - похвали. "
            "Если чего-то не хватает в рационе - предложи.\n\n"
            "Верни ТОЛЬКО JSON объект в формате:\n"
            "{{\"warnings\": [\"⚠️ предупреждение 1\", \"⚠️ предупреждение 2\"], "
            "\"recommendations\": [\"✅ рекомендация 1\", \"✅ рекомендация 2\"], "
            "\"missing\": [\"💡 предложение 1\", \"💡 предложение 2\"]}}\n"
            "Если нет предупреждений/рекомендаций/предложений - верни пустой массив."
        )

        for model in cls.MODELS:
            result = await cls._call_model(model, prompt)
            if result:
                return result

        return None

    @staticmethod
    async def _call_model(model: str, prompt: str) -> dict[str, Any] | None:
        """Call AI model for consultation.

        Args:
            model: Model name
            prompt: Prompt text

        Returns:
            Parsed JSON response or None if failed

        """
        import aiohttp

        from config import settings

        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://foodflow.app",
            "X-Title": "FoodFlow Bot",
        }

        payload = {"model": model, "messages": [{"role": "user", "content": prompt}]}

        import asyncio

        for attempt in range(3):
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers=headers,
                        json=payload,
                        timeout=45,
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            content = result["choices"][0]["message"]["content"]
                            # Clean markdown
                            content = content.replace("```json", "").replace("```", "").strip()
                            # Try to extract JSON if there's extra text
                            import re

                            json_match = re.search(r"\{.*\}", content, re.DOTALL)
                            import html
                            if json_match:
                                content = json_match.group(0)
                            
                            parsed_json = json.loads(content)
                            
                            # Sanitize all strings in the JSON to be safe for HTML parse mode
                            if isinstance(parsed_json, dict):
                                for key in ["warnings", "recommendations", "missing"]:
                                    if key in parsed_json and isinstance(parsed_json[key], list):
                                        parsed_json[key] = [html.escape(str(item)) for item in parsed_json[key]]
                            
                            return parsed_json
                        else:
                            logger.warning(
                                f"Consultant AI ({model}) attempt {attempt+1}/3 failed: {response.status}"
                            )
                            if attempt < 2:
                                await asyncio.sleep(0.5)
                                continue
                except Exception as e:
                    logger.error(
                        f"Exception in Consultant AI ({model}) attempt {attempt+1}/3: {e}"
                    )
                    if attempt < 2:
                        await asyncio.sleep(0.5)
                        continue
        return None

    @staticmethod
    def _calculate_simple_recommendations(
        product: Product, user_settings: UserSettings
    ) -> dict[str, Any]:
        """Calculate simple recommendations based on rules (fallback).

        Args:
            product: Product to analyze
            user_settings: User profile

        Returns:
            Dictionary with simple recommendations

        """
        warnings: list[str] = []
        recommendations: list[str] = []
        missing: list[str] = []

        # Check allergies
        if user_settings.allergies:
            allergies_list = [
                a.strip().lower() for a in user_settings.allergies.split(",")
            ]
            product_name_lower = product.name.lower()
            for allergy in allergies_list:
                if allergy in product_name_lower:
                    warnings.append(f"⚠️ В продукте может содержаться {allergy} (аллергия)")

        # Check calories based on goal
        if user_settings.goal == "lose_weight":
            if product.calories > 400:
                warnings.append("⚠️ Высокая калорийность для похудения")
        elif user_settings.goal == "gain_mass":
            if product.calories < 200 and product.protein < 10:
                missing.append("💡 Для набора массы нужны более калорийные продукты с белком")

        # Check protein
        if product.protein > 15:
            recommendations.append("✅ Хороший источник белка")

        # Check category
        unhealthy_categories = ["Сладости", "Фастфуд", "Газированные напитки"]
        if product.category in unhealthy_categories and user_settings.goal in (
            "lose_weight",
            "healthy",
        ):
            warnings.append(f"⚠️ {product.category} не рекомендуется для вашей цели")

        return {
            "warnings": warnings,
            "recommendations": recommendations,
            "missing": missing,
        }









