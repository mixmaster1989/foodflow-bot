"""Module for product name normalization and categorization.

Contains:
- NormalizationService: Normalizes OCR-extracted product names using AI models
"""
import json
import logging
import re
from typing import Any

import aiohttp

from config import settings

logger = logging.getLogger(__name__)


class NormalizationService:
    """Normalize and categorize product names from OCR results.

    Uses multiple AI models to correct OCR errors, identify real product names,
    preserve brand names and weights, categorize products, and estimate calories.
    """

    MODELS: list[str] = [
        "perplexity/sonar",                                    # Free 1: Best quality with web search
        "mistralai/mistral-small-3.2-24b-instruct:free",      # Free 2: Fast & Smart
        "qwen/qwen2.5-vl-32b-instruct:free",                 # Free 3: Working Fallback
        "google/gemini-2.5-flash-lite-preview-09-2025",       # Paid 1: Cheapest ($0.00016)
        "openai/gpt-4.1-mini",                                 # Paid 2: Fastest (471ms)
    ]

    @classmethod
    async def normalize_products(cls, raw_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Normalize product names and add category/calories/fiber information."""
        if not raw_items:
            return []

        # Prepare the list for the prompt
        items_str = "\n".join([f"- {item.get('name', 'Unknown')}" for item in raw_items])

        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://foodflow.app",
            "X-Title": "FoodFlow Bot"
        }

        prompt = (
            "You are a smart receipt assistant. I have a list of raw product names from a Russian grocery receipt. "
            "Many names are abbreviated or contain OCR errors (e.g., 'СЕЛЬКИ насло' -> 'Масло подсолнечное', 'Шинка ВЕЛОСИПЕД' -> 'Ветчина'). "
            "Your task:\n"
            "1. Identify the real product name using web search if needed.\n"
            "2. PRESERVE brand names if recognizable (e.g., 'МИЛКА' -> 'Милка', 'Lays' -> 'Lays').\n"
            "3. PRESERVE weight/volume if present (e.g., '450г', '1л', '200мл').\n"
            "4. Categorize it (e.g., Молочные продукты, Мясо, Овощи, Снеки, Бакалея).\n"
            "5. Find nutrition per 100g: Calories, Protein, Fat, Carbs, Fiber (Клетчатка).\n"
            "6. Return a JSON object with a list of normalized items. Keep the original order.\n"
            "IMPORTANT: All names and categories MUST be in RUSSIAN language.\n"
            "IMPORTANT: If a product has NO fiber (e.g. water, oil, meat, sugar), set \"fiber\": 0 explicitly!\n\n"
            "Input List:\n"
            f"{items_str}\n\n"
            "CRITICAL OUTPUT REQUIREMENTS:\n"
            "- Return ONLY the JSON object. Nothing before it, nothing after it.\n"
            "- Do NOT include markdown formatting (no ```json or ```).\n"
            "- Do NOT add explanations, comments, or any text after the JSON.\n"
            "- Your response must start with { and end with }.\n"
            "- Example of CORRECT response: {\"normalized\": [{\"original\": \"...\", \"name\": \"...\", \"category\": \"...\", \"calories\": 250, \"protein\": 10.5, \"fat\": 5.2, \"carbs\": 30.0, \"fiber\": 1.2}]}\n"
            "- Example of WRONG response: {\"normalized\": [...]}\n**Пояснения:** ...\n\n"
            "Output Format (JSON ONLY, NO TEXT BEFORE OR AFTER):\n"
            "{\"normalized\": [{\"original\": \"...\", \"name\": \"Название с брендом и весом (RU)\", \"category\": \"Категория (RU)\", \"calories\": 0, \"protein\": 0, \"fat\": 0, \"carbs\": 0, \"fiber\": 0}]}"
        )

        import asyncio

        for model in cls.MODELS:
            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            }

            # Retry logic: 3 attempts with 0.5s delay
            for attempt in range(3):
                async with aiohttp.ClientSession() as session:
                    try:
                        async with session.post(
                            "https://openrouter.ai/api/v1/chat/completions",
                            headers=headers,
                            json=payload,
                            timeout=60
                        ) as response:
                            if response.status == 200:
                                result = await response.json()
                                content = result['choices'][0]['message']['content']
                                
                                # Robust JSON extraction
                                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
                                if json_match:
                                    content = json_match.group(1)
                                else:
                                    content = content.replace("```json", "").replace("```", "").strip()
                                    first_brace = content.find('{')
                                    last_brace = content.rfind('}')
                                    if first_brace >= 0 and last_brace >= 0:
                                        content = content[first_brace:last_brace+1]

                                try:
                                    parsed = json.loads(content)
                                    normalized_map = {item['original']: item for item in parsed.get('normalized', [])}

                                    final_items = []
                                    for item in raw_items:
                                        raw_name = item.get('name', 'Unknown')
                                        norm_data = normalized_map.get(raw_name, {})

                                        final_items.append({
                                            "name": norm_data.get('name', raw_name), 
                                            "price": item.get('price', 0.0),
                                            "quantity": item.get('quantity', 1.0),
                                            "category": norm_data.get('category', 'Uncategorized'),
                                            "calories": norm_data.get('calories', 0),
                                            "protein": norm_data.get('protein', 0),
                                            "fat": norm_data.get('fat', 0),
                                            "carbs": norm_data.get('carbs', 0),
                                            "fiber": norm_data.get('fiber', 0) # NEW: Fiber
                                        })
                                    return final_items

                                except json.JSONDecodeError:
                                    logger.error(f"Failed to parse Normalization JSON ({model}): {content}")
                                    break
                            else:
                                logger.warning(f"Normalization API ({model}) attempt {attempt+1}/3 failed: {response.status}")
                                if attempt < 2:
                                    await asyncio.sleep(0.5)
                                    continue
                    except Exception as e:
                        logger.error(f"Exception in Normalization Service ({model}) attempt {attempt+1}/3: {e}")
                        if attempt < 2:
                            await asyncio.sleep(0.5)
                            continue

            logger.warning(f"Model {model} failed, switching to next...")

        return raw_items

    @classmethod
    async def analyze_food_intake(cls, description: str) -> dict:
        """Analyze food intake with weight detection.
        
        Returns dict with:
        - name: food name
        - calories, protein, fat, carbs, fiber: KBJU values
        - weight_grams: detected weight or None
        - weight_missing: True if no weight specified
        """
        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://foodflow.app",
            "X-Title": "FoodFlow Bot"
        }

        prompt = f'''Analyze this food intake description: "{description}"

TASK:
1. Extract the food name (in Russian)
2. Extract the "base_name" (Essence) - the generic name of the product without weight, brand, or adjectives if possible (e.g. "Яблоко 150г" -> "Яблоко", "Творог 5% Простоквашино" -> "Творог 5%").
3. Detect if weight/portion is specified.
4. Calculate KBJU based on the specified weight.

WEIGHT DETECTION RULES:
- "банан 150" = 150 grams
- "банан 150г" = 150 grams
- "банан 150 грамм" = 150 grams
- "2 яйца" = 2 pieces (~120g total)
- "тарелка борща" = ~300g (estimate)
- "большая порция" = ~400g (estimate)
- "банан" (no weight) = weight_missing: true, return per 100g

RETURN JSON ONLY:
{{
  "name": "Название продукта (RU)",
  "base_name": "Суть продукта (RU)",
  "weight_grams": 150,
  "weight_missing": false,
  "calories": 134,
  "protein": 1.7,
  "fat": 0.5,
  "carbs": 34.2,
  "fiber": 3.9
}}

If weight is NOT specified:
{{
  "name": "Банан",
  "base_name": "Банан",
  "weight_grams": null,
  "weight_missing": true,
  "calories": 89,
  "protein": 1.1,
  "fat": 0.3,
  "carbs": 22.8,
  "fiber": 2.6
}}

CRITICAL: Return ONLY JSON, no markdown, no explanations.'''

        import asyncio
        import aiohttp

        for model in cls.MODELS[:3]:  # Use first 3 models only
            for attempt in range(2):
                try:
                    payload = {
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.1
                    }
                    
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            "https://openrouter.ai/api/v1/chat/completions",
                            headers=headers,
                            json=payload,
                            timeout=aiohttp.ClientTimeout(total=30)
                        ) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                content = data["choices"][0]["message"]["content"].strip()
                                
                                # Clean JSON
                                if content.startswith("```"):
                                    content = content.split("```")[1]
                                    if content.startswith("json"):
                                        content = content[4:]
                                content = content.strip()
                                
                                result = json.loads(content)
                                logger.info(f"Food intake analyzed: {result}")
                                return result
                except Exception as e:
                    logger.error(f"analyze_food_intake error ({model}): {e}")
                    if attempt < 1:
                        await asyncio.sleep(0.3)
                        continue
        
        # Fallback
        return {
            "name": description,
            "weight_grams": None,
            "weight_missing": True,
            "calories": 100,
            "protein": 5,
            "fat": 3,
            "carbs": 15,
            "fiber": 1
        }
