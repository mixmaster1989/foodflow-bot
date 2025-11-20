import base64
import json
import logging
import aiohttp
from FoodFlow.config import settings


logger = logging.getLogger(__name__)


class LabelOCRService:
    MODEL = "google/gemini-2.0-flash-exp:free"

    @staticmethod
    async def parse_label(image_bytes: bytes) -> dict | None:
        """
        Extracts product information from a label photo.
        Expected JSON structure:
        {
            "name": "Полное название",
            "brand": "Бренд",
            "weight": "500 г",
            "calories": 250,
            "protein": 12.5,
            "fat": 10.2,
            "carbs": 30.1
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

        payload = {
            "model": LabelOCRService.MODEL,
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

                    logger.error(f"Label OCR failed: {await response.text()}")
                    return None
            except Exception as exc:
                logger.error(f"Label OCR exception: {exc}")
                return None

