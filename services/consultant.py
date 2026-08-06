"""Module for AI-powered product consultation service.

Contains:
- ConsultantService: Analyzes products based on user profile and provides recommendations
"""
import json
import logging
from typing import Any

from database.models import Product, UserSettings
from services.ai import AIService
from utils.i18n import t, get_locale

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
        locale = get_locale()

        # Build user profile description
        gender_text = t("consultant.profile_gender_male", locale=locale) if user_settings.gender == "male" else t("consultant.profile_gender_female", locale=locale)
        goal_text = {
            "lose_weight": t("consultant.goal_lose_weight", locale=locale),
            "maintain": t("consultant.goal_maintain", locale=locale),
            "healthy": t("consultant.goal_healthy", locale=locale),
            "gain_mass": t("consultant.goal_gain_mass", locale=locale),
        }.get(user_settings.goal, t("consultant.goal_default", locale=locale))

        context_text = {
            "receipt": t("consultant.context_receipt", locale=locale),
            "fridge": t("consultant.context_fridge", locale=locale),
            "shopping_list": t("consultant.context_shopping_list", locale=locale),
            "shopping": t("consultant.context_shopping", locale=locale),
            "general": t("consultant.context_general", locale=locale),
        }.get(context, t("consultant.context_general", locale=locale))

        # Build product description
        product_info = t(
            "consultant.product_format",
            locale=locale,
            name=product.name,
            category=product.category or t("shopping_list.curator_no_data", locale=locale, default="No especificada"),
            calories=product.calories,
            protein=product.protein,
            fat=product.fat,
            carbs=product.carbs
        )

        allergies_text = (
            t("consultant.allergies_format", locale=locale, allergies=user_settings.allergies)
            if user_settings.allergies
            else t("consultant.no_allergies", locale=locale)
        )

        snapshot_text = ""
        if fridge_snapshot:
            total = fridge_snapshot.get("totals", {})
            items = fridge_snapshot.get("items", [])
            
            snap_items_str = "\n".join(f"• {i}" for i in items) if items else t("consultant.fridge_snapshot_no_data", locale=locale)
            
            snapshot_text = (
                t("consultant.fridge_snapshot_title", locale=locale) +
                t("consultant.fridge_snapshot_count", locale=locale, count=len(items)) +
                snap_items_str + "</blockquote>" +
                t("consultant.fridge_snapshot_totals", locale=locale) +
                f"<blockquote>🔥 <code>{total.get('calories', 0):.0f}</code> | 🥩 <code>{total.get('protein', 0):.1f}</code> | 🥑 <code>{total.get('fat', 0):.1f}</code> | 🍞 <code>{total.get('carbs', 0):.1f}</code></blockquote>\n"
            )

        prompt = t(
            "consultant.prompt_instructions",
            locale=locale,
            gender=gender_text,
            height=user_settings.height,
            weight=user_settings.weight,
            goal=goal_text,
            calorie_goal=user_settings.calorie_goal,
            protein_goal=user_settings.protein_goal,
            fat_goal=user_settings.fat_goal,
            carb_goal=user_settings.carb_goal,
            allergies_text=allergies_text,
            product_info=product_info,
            snapshot_text=snapshot_text + chr(10) if snapshot_text else '',
            context_text=context_text
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
                        proxy=settings.openrouter_proxy,
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

        locale = get_locale()
        # Check allergies
        if user_settings.allergies:
            allergies_list = [
                a.strip().lower() for a in user_settings.allergies.split(",")
            ]
            product_name_lower = product.name.lower()
            for allergy in allergies_list:
                if allergy in product_name_lower:
                    warnings.append(t("consultant.fallback_allergy", locale=locale, allergy=allergy))

        # Check calories based on goal
        if user_settings.goal == "lose_weight":
            if product.calories > 400:
                warnings.append(t("consultant.fallback_high_cal", locale=locale))
        elif user_settings.goal == "gain_mass":
            if product.calories < 200 and product.protein < 10:
                missing.append(t("consultant.fallback_gain_mass", locale=locale))

        # Check protein
        if product.protein > 15:
            recommendations.append(t("consultant.fallback_protein", locale=locale))

        # Check category
        unhealthy_categories = ["Сладости", "Фастфуд", "Газированные напитки", "Sweets", "Fast food", "Soft drinks"]
        if product.category in unhealthy_categories and user_settings.goal in (
            "lose_weight",
            "healthy",
        ):
            warnings.append(t("consultant.fallback_unhealthy", locale=locale, category=product.category))

        return {
            "warnings": warnings,
            "recommendations": recommendations,
            "missing": missing,
        }









