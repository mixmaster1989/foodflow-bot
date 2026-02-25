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
    """

    MODELS: list[str] = [
        # Free first, but retry quickly then jump to paid
        "qwen/qwen2.5-vl-32b-instruct:free",
        # Paid earlier to avoid long stalls on free limits
        "google/gemini-2.5-flash-lite",
        # Remaining fallbacks
        "google/gemini-2.0-flash-exp:free",
        "mistralai/mistral-small-3.2-24b-instruct:free",
        "mistralai/pixtral-12b",
        "qwen/qwen-vl-plus",
    ]

    @classmethod
    async def parse_label(cls, image_bytes: bytes) -> dict[str, Any] | None:
        """Parse label image and extract product information."""
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
            "\"carbs\": 0, "
            "\"fiber\": 0}. "
            "Calories/Macros should be per 100g/ml if available. "
            "Look for 'Клетчатка', 'Пищевые волокна', 'Fiber' for the fiber field. "
            "If data is missing, set the value to 0 if reasonable (e.g. fiber in oil), or null if unsure."
        )

        import asyncio
        RETRY_ATTEMPTS = 3
        RETRY_DELAY = 1.0  # seconds

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

            # Retry logic: 3 attempts with 1s delay
            for attempt in range(RETRY_ATTEMPTS):
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
                            if attempt < RETRY_ATTEMPTS - 1:
                                await asyncio.sleep(RETRY_DELAY)
                                continue
                    except Exception as exc:
                        logger.error(f"Label OCR exception ({model}) attempt {attempt+1}/3: {exc}")
                        if attempt < RETRY_ATTEMPTS - 1:
                            await asyncio.sleep(RETRY_DELAY)
                            continue

            # If we get here, this model failed 3 times, try next model
            logger.warning(f"Model {model} failed all attempts, switching to next...")

        return None
