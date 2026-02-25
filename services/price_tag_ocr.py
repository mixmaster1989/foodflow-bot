"""Module for price tag OCR processing.

Contains:
- PriceTagOCRService: Extract product name, price, volume, store from price tag images
"""
import base64
import json
import logging
from typing import Any

import aiohttp

from config import settings

logger = logging.getLogger(__name__)


class PriceTagOCRService:
    """Extract price information from price tag photos.

    Uses multiple AI models to extract product name, price, volume,
    store name, and date from price tag images.

    Attributes:
        MODELS: List of fallback models ordered by quality (best first)

    Example:
        >>> service = PriceTagOCRService()
        >>> data = await service.parse_price_tag(image_bytes)
        >>> print(data['product_name'])
        'Молоко 3.2%'

    """

    MODELS: list[str] = [
        # Free models (try first)
        "qwen/qwen2.5-vl-32b-instruct:free",
        "google/gemini-2.0-flash-exp:free",
        "mistralai/mistral-small-3.2-24b-instruct:free",
        "nvidia/nemotron-nano-12b-v2-vl:free",

        # Paid models (fallback when free models are rate-limited)
        "google/gemini-2.5-flash-lite",               # Paid 1: Cheapest Google ($0.10/$0.40)
        "mistralai/pixtral-12b",                      # Paid 2: Cheapest overall ($0.10/$0.10)
        "qwen/qwen-vl-plus",                          # Paid 3: Best accuracy ($0.21/$0.63)
    ]

    @classmethod
    async def parse_price_tag(cls, image_bytes: bytes) -> dict[str, Any] | None:
        """Parse price tag image and extract product information.

        Args:
            image_bytes: Raw image bytes (JPEG/PNG format)

        Returns:
            Dictionary with keys: product_name, volume, price, store, date
            Or None if all models fail

        Note:
            Tries models in order until one succeeds. Each model has 3 retry attempts.

        """
        for model in cls.MODELS:
            result = await cls._call_model(model, image_bytes)
            if result:
                return result
        return None

    @staticmethod
    async def _call_model(model: str, image_bytes: bytes) -> dict[str, Any] | None:
        """Call specific OCR model to extract price tag information.

        Args:
            model: Model identifier to use
            image_bytes: Raw image bytes

        Returns:
            Dictionary with keys: product_name, volume, price, store, date
            Or None if model fails

        Note:
            Retries 3 times with 0.5s delay between attempts.

        """
        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://foodflow.app",
            "X-Title": "FoodFlow Bot"
        }

        base64_image = base64.b64encode(image_bytes).decode("utf-8")

        prompt = (
            "You are scanning a Russian price tag photo from a grocery store. "
            "Return ONLY JSON (no markdown) with the following keys: "
            "{\"product_name\": \"Название товара БЕЗ объема (RU)\", "
            "\"volume\": \"Объем/вес с единицами (например: 500 мл, 1 кг, 300 г)\", "
            "\"price\": 0.0, "
            "\"store\": \"Название магазина (если указано)\", "
            "\"date\": \"YYYY-MM-DD (если указано)\"}. "
            "IMPORTANT: Extract volume/weight as a SEPARATE field, not in product_name. "
            "If data is missing, set the value to null. "
            "Price should be a float number in rubles."
        )

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

        import asyncio

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
                            return json.loads(content)

                        logger.warning(f"Price Tag OCR ({model}) attempt {attempt+1}/3 failed: {response.status}")
                        if attempt < 2:
                            await asyncio.sleep(0.5)
                            continue

                except Exception as exc:
                    logger.error(f"Price Tag OCR exception ({model}) attempt {attempt+1}/3: {exc}")
                    if attempt < 2:
                        await asyncio.sleep(0.5)
                        continue
        return None
