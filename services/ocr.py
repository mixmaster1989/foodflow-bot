"""Module for optical character recognition and receipt processing.

Contains:
- OCRService: Main OCR processing engine with multiple model fallback
"""
import base64
import json
import logging
from typing import Any

import aiohttp

from config import settings

logger = logging.getLogger(__name__)

class OCRService:
    """Handle receipt image recognition using multiple AI models.

    Models are tried in order until one succeeds. Supports both free and paid
    models with automatic fallback mechanism.

    Attributes:
        MODELS: List of fallback models ordered by quality (best first)

    Example:
        >>> ocr = OCRService()
        >>> result = await ocr.parse_receipt(image_bytes)
        >>> print(result['items'])
        [{'name': 'Молоко', 'price': 100.0, 'quantity': 1.0}, ...]

    """

    MODELS: list[str] = [
        "qwen/qwen2.5-vl-32b-instruct:free",          # Top 1: Best quality
        "google/gemini-2.0-flash-exp:free",           # Top 2: Fast & Smart
        "mistralai/mistral-small-3.2-24b-instruct:free", # Top 3: Working & Multimodal
        "nvidia/nemotron-nano-12b-v2-vl:free",        # Top 4: Working Fallback
        "openai/gpt-4o-mini",                         # Paid Fallback
    ]

    @staticmethod
    async def _call_openrouter(model: str, image_bytes: bytes) -> dict[str, Any] | None:
        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://foodflow.app",
            "X-Title": "FoodFlow Bot"
        }

        base64_image = base64.b64encode(image_bytes).decode('utf-8')

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Analyze this receipt. Return a JSON object with a list of items (name, price, quantity) and the total amount. Do not include markdown formatting, just raw JSON. Format: {\"items\": [{\"name\": \"str\", \"price\": float, \"quantity\": float}], \"total\": float}"
                        },
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
                            if 'error' in result:
                                 logger.error(f"Model {model} returned API error: {result['error']}")
                                 return None

                            content = result['choices'][0]['message']['content']
                            # Clean markdown if present
                            content = content.replace("```json", "").replace("```", "").strip()
                            return json.loads(content)
                        else:
                            logger.warning(f"Model {model} attempt {attempt+1}/3 failed with status {response.status}")
                            if attempt < 2:
                                await asyncio.sleep(0.5)
                                continue
                            return None
                except Exception as e:
                    logger.error(f"Exception calling {model} (attempt {attempt+1}/3): {e}")
                    if attempt < 2:
                        await asyncio.sleep(0.5)
                        continue
                    return None
        return None

    @classmethod
    async def parse_receipt(cls, image_bytes: bytes) -> dict[str, Any]:
        """Parse receipt image and extract product items.

        Args:
            image_bytes: Raw image bytes (JPEG/PNG format)

        Returns:
            Dictionary with 'items' (list of dicts with 'name', 'price', 'quantity')
            and 'total' (float) keys

        Raises:
            Exception: If all OCR models fail to process the image

        Note:
            Tries models in order: Qwen → Gemini → Mistral → Nemotron → GPT-4o-mini
            Each model has 3 retry attempts with 0.5s delay between retries

        """
        for model in cls.MODELS:
            logger.info(f"Trying OCR model: {model}")
            result = await cls._call_openrouter(model, image_bytes)
            if result:
                return result
            logger.warning(f"Model {model} failed. Trying next...")

        raise Exception("All OCR models failed. Please try again later or check the logs.")
