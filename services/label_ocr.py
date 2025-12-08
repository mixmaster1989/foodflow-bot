"""Module for product label OCR processing.

Contains:
- LabelOCRService: Extract product name, brand, weight, and nutrition info from label images
"""
import base64
import json
import logging
from typing import Any

import aiohttp

from config import settings

logger = logging.getLogger(__name__)


class LabelOCRService:
    """Extract product information from food label photos.

    Uses multiple AI models to extract product name, brand, weight,
    and nutrition values (calories, protein, fat, carbs) from label images.

    Attributes:
        MODELS: List of fallback models ordered by quality (best first)

    Example:
        >>> service = LabelOCRService()
        >>> data = await service.parse_label(image_bytes)
        >>> print(data['name'])
        'Молоко 3.2%'

    """

    MODELS: list[str] = [
        # Free models (try first)
        "qwen/qwen2.5-vl-32b-instruct:free",          # Top 1: Best quality
        "google/gemini-2.0-flash-exp:free",           # Top 2: Fast & Smart
        "mistralai/mistral-small-3.2-24b-instruct:free", # Top 3: Working & Multimodal

        # Paid models (fallback when free models are rate-limited)
        "google/gemini-2.5-flash-lite",               # Paid 1: Cheapest Google ($0.10/$0.40)
        "mistralai/pixtral-12b",                      # Paid 2: Cheapest overall ($0.10/$0.10)
        "qwen/qwen-vl-plus",                          # Paid 3: Best accuracy ($0.21/$0.63)
    ]

    @classmethod
    async def parse_label(cls, image_bytes: bytes) -> dict[str, Any] | None:
        """Parse label image and extract product information.

        Args:
            image_bytes: Raw image bytes (JPEG/PNG format)

        Returns:
            Dictionary with keys: name, brand, weight, calories, protein, fat, carbs
            Or None if all models fail

        Note:
            Tries models in order until one succeeds. Each model has 3 retry attempts.
            Calories should be per 100g/ml if available.

        """
        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://foodflow.app",
            "X-Title": "FoodFlow Bot"
        }

        base64_image = base64.b64encode(image_bytes).decode("utf-8")

        prompt = (
            "You are scanning a Russian food label photo. "
            "Return ONLY JSON (no markdown) with the following keys: "
            "{\"name\": \"Название товара (RU)\", "
            "\"brand\": \"Бренд (если указан)\", "
            "\"weight\": \"Вес/объем с единицами\", "
            "\"calories\": 0, "
            "\"protein\": 0, "
            "\"fat\": 0, "
            "\"carbs\": 0}. "
            "Calories should be per 100g/ml if available. "
            "If data is missing, set the value to null."
        )

        import asyncio

        for model in cls.MODELS:
            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
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
                                content = result["choices"][0]["message"]["content"]
                                content = content.replace("```json", "").replace("```", "").strip()
                                parsed_data = json.loads(content)
                                logger.info(f"Label OCR ({model}) successfully parsed label: {parsed_data.get('name', 'Unknown')}")
                                return parsed_data

                            logger.warning(f"Label OCR ({model}) attempt {attempt+1}/3 failed: {response.status}")
                            if attempt < 2:
                                await asyncio.sleep(0.5)
                                continue
                    except Exception as exc:
                        logger.error(f"Label OCR exception ({model}) attempt {attempt+1}/3: {exc}")
                        if attempt < 2:
                            await asyncio.sleep(0.5)
                            continue

            # If we get here, this model failed 3 times, try next model
            logger.warning(f"Model {model} failed all attempts, switching to next...")

        return None


