import base64
import json
import logging
import aiohttp
from FoodFlow.config import settings


logger = logging.getLogger(__name__)


class PriceTagOCRService:
    MODEL = "google/gemini-2.0-flash-exp:free"

    @staticmethod
    async def parse_price_tag(image_bytes: bytes) -> dict | None:
        """
        Extracts price information from a price tag photo.
        Expected JSON structure:
        {
            "product_name": "Молоко 3.2% 1л",
            "price": 89.99,
            "store": "Пятёрочка",
            "date": "2025-11-20"
        }
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
            "{\"product_name\": \"Полное название товара (RU)\", "
            "\"price\": 0.0, "
            "\"store\": \"Название магазина (если указано)\", "
            "\"date\": \"YYYY-MM-DD (если указано)\"}. "
            "If data is missing, set the value to null. "
            "Price should be a float number in rubles."
        )

        payload = {
            "model": PriceTagOCRService.MODEL,
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

                    logger.error(f"Price Tag OCR failed: {await response.text()}")
                    return None
            except Exception as exc:
                logger.error(f"Price Tag OCR exception: {exc}")
                return None
