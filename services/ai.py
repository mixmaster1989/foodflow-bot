"""Module for AI-powered recipe generation.

Contains:
- AIService: Generates recipes based on available ingredients and category
"""
import asyncio
import json
import logging
from typing import Any, Optional

import aiohttp

from config import settings

logger = logging.getLogger(__name__)


class AIService:
    """Generate recipes using AI models based on available ingredients.
    """

    MODELS: list[str] = [
        "openai/gpt-oss-120b:medium",  # User‑selected higher‑capacity model
        "mistralai/mistral-small-3.2-24b-instruct:free", # Working & Smart
        "qwen/qwen3-30b-a3b:free",                        # Working & New
        "google/gemma-3-27b-it:free",                     # Good but unstable
        "deepseek/deepseek-chat-v3-0324:free",            # Good but unstable
        "openai/gpt-oss-20b:free"                         # Working fallback
    ]

    GUIDE_MODELS: list[str] = [
        "nvidia/nemotron-3-super-120b-a12b:free",         # Primary (Powerful 120B)
        "google/gemma-4-31b-it:free",                      # Fallback (User insisted)
        "qwen/qwen-2.5-72b-instruct:free",                # Backup 2
        "google/gemini-2.0-flash-lite-preview-09-2025"    # Paid fallback
    ]

    @classmethod
    async def generate_recipes(cls, ingredients: list[str], category: str, user_settings: Any = None) -> dict[str, Any] | None:
        """Generate recipes based on available ingredients and category."""
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

    @staticmethod
    async def recognize_product_from_image(image_bytes: bytes) -> dict[str, Any] | None:
        """Recognize product from photo and get average KBZHU + Fiber."""
        import base64
        import re

        from services.label_ocr import LabelOCRService

        # First try: parse as label (has KBZHU on it)
        label_data = await LabelOCRService.parse_label(image_bytes)
        if label_data and label_data.get("name") and label_data.get("calories"):
            # If label service returned data, checking if it has fiber.
            # If not, we might want to augment it, but LabelOCR should be updated too.
            return label_data

        # Second try: recognize product and get average KBZHU
        base64_image = base64.b64encode(image_bytes).decode("utf-8")

        prompt = (
            "Ты видишь фото продукта питания. Определи что это за продукт и верни усредненные значения КБЖУ и Клетчатки (fiber).\n\n"
            "Верни ТОЛЬКО JSON объект (без markdown) в формате:\n"
            '{"name": "Название продукта на русском", "brand": null, "weight": null, '
            '"calories": 0, "protein": 0.0, "fat": 0.0, "carbs": 0.0, "fiber": 0.0}\n\n'
            "calories, protein, fat, carbs, fiber - это усредненные значения на 100г для этого типа продукта.\n"
            "ВАЖНО: Если продукт не содержит клетчатки (вода, масло, сахар, мясо без гарнира и т.д.), в поле \"fiber\" укажи строго 0!\n"
            "Например, для яблока: calories=52, protein=0.3, fat=0.2, carbs=14, fiber=2.4.\n"
            "Если не можешь определить - верни null для всех полей."
        )

        models = [
            "qwen/qwen2.5-vl-32b-instruct:free",
            "qwen/qwen3.6-plus:free",
            "openai/gpt-4.1-mini",
        ]

        # Use _call_model logic but adapted for vision
        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://foodflow.app",
            "X-Title": "FoodFlow Bot",
        }

        retry_attempts = 3
        retry_delay = 1.0

        for model in models:
            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}},
                        ],
                    }
                ],
            }
            for attempt in range(retry_attempts):
                async with aiohttp.ClientSession() as session:
                    try:
                        async with session.post(
                            "https://openrouter.ai/api/v1/chat/completions",
                            headers=headers,
                            json=payload,
                            timeout=35, # Moderate timeout for vision
                        ) as response:
                            if response.status == 200:
                                result = await response.json()
                                if not result or 'choices' not in result:
                                    logger.warning(f"Empty AI result ({model}) attempt {attempt+1}")
                                    continue

                                content = result["choices"][0]["message"]["content"]
                                content = content.replace("```json", "").replace("```", "").strip()

                                # Robust JSON extraction
                                json_match = re.search(r"\{.*\}", content, re.DOTALL)
                                if json_match:
                                    content = json_match.group(0)

                                try:
                                    data = json.loads(content)
                                    # SUCCESS CRITERIA: Must have a name and it shouldn't be null/empty
                                    if data and data.get("name") and data.get("name") not in ["Неизвестное блюдо", "Неизвестно"]:
                                        logger.info(f"✅ AI ({model}) recognized: {data.get('name')}")
                                        return data
                                    else:
                                        logger.warning(f"AI ({model}) returned unknown/null result on attempt {attempt+1}: {content}")
                                        # Force retry since it failed to identify properly
                                        if attempt < retry_attempts - 1:
                                            await asyncio.sleep(retry_delay)
                                            continue
                                except json.JSONDecodeError as je:
                                    logger.warning(f"JSON Parse Error ({model}) attempt {attempt+1}: {je}")
                                    if attempt < retry_attempts - 1:
                                        await asyncio.sleep(retry_delay)
                                        continue
                            else:
                                error_text = await response.text()
                                logger.warning(f"AI Error {response.status} ({model}) attempt {attempt+1}: {error_text}")
                                if attempt < retry_attempts - 1:
                                    await asyncio.sleep(retry_delay)
                                    continue
                    except Exception as e:
                        logger.error(f"Exc in AI Vision ({model}) attempt {attempt+1}: {e}")
                        if attempt < retry_attempts - 1:
                            await asyncio.sleep(retry_delay)
                        continue
        return None
    @classmethod
    async def get_completion(cls, prompt: str, model: Optional[str] = None) -> str | None:
        """Get a generic text completion from AI (G guide/general)."""
        if model:
            target_models = [model]
        else:
            target_models = cls.GUIDE_MODELS
            
        for target_model in target_models:
            headers = {
                "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://foodflow.app",
                "X-Title": "FoodFlow Bot"
            }

            payload = {
                "model": target_model,
                "messages": [{"role": "user", "content": prompt}]
            }

            async with aiohttp.ClientSession() as session:
                try:
                    async with session.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers=headers,
                        json=payload,
                        timeout=15
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            return result['choices'][0]['message']['content'].strip()
                        else:
                            logger.warning(f"AI Completion ({target_model}) failed: {response.status}")
                except Exception as e:
                    logger.error(f"Exception in AI Completion ({target_model}): {e}")
        return None

    @classmethod
    async def get_completion_stream(cls, prompt: str, model: Optional[str] = None):
        """Get a streamed text completion from AI."""
        import json
        if model:
            target_models = [model]
        else:
            target_models = cls.GUIDE_MODELS
            
        for target_model in target_models:
            headers = {
                "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://foodflow.app",
                "X-Title": "FoodFlow Bot"
            }

            payload = {
                "model": target_model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": True,
                "temperature": 0.8
            }

            # Retry each model 3 times before moving to next fallback
            for attempt in range(3):
                async with aiohttp.ClientSession() as session:
                    try:
                        async with session.post(
                            "https://openrouter.ai/api/v1/chat/completions",
                            headers=headers,
                            json=payload,
                            timeout=30
                        ) as response:
                            if response.status != 200:
                                logger.warning(f"AI Stream ({target_model}) attempt {attempt+1} failed: {response.status}")
                                if attempt < 2:
                                    await asyncio.sleep(0.5)
                                    continue
                                break # Move to next model
                                
                            async for line in response.content:
                                if not line:
                                    continue
                                
                                decoded_line = line.decode("utf-8").strip()
                                if decoded_line.startswith("data: "):
                                    data_str = decoded_line[6:].strip()
                                    if data_str == "[DONE]":
                                        break
                                    
                                    try:
                                        data = json.loads(data_str)
                                        if "choices" in data and len(data["choices"]) > 0:
                                            delta = data["choices"][0].get("delta", {})
                                            if "content" in delta:
                                                yield delta["content"]
                                    except Exception:
                                        continue
                            return # Stream finished successfully
                    except Exception as e:
                        logger.error(f"Exception in AI Stream ({target_model}) attempt {attempt+1}: {e}")
                        if attempt < 2:
                            await asyncio.sleep(0.5)
                            continue
                        break # Move to next model
        
        # If all models fail, yield empty
        yield ""
