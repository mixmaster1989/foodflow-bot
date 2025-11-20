import base64
import aiohttp
import json
import logging
from FoodFlow.config import settings

logger = logging.getLogger(__name__)

class OCRService:
    """
    Models ordered by quality:
    1) openai/gpt-4o-mini — лучший результат (по тесту 20.11.2025).
    2) openai/gpt-4o-mini-2024-07-18 — тот же движок, но прошлый релиз.
    3) Дальше прежние бесплатные fallback'и.
    """
    MODELS = [
        "openai/gpt-4o-mini",
        "openai/gpt-4o-mini-2024-07-18",
        "google/gemini-2.0-flash-exp:free",
        "google/gemma-3-27b-it:free",
        "mistralai/mistral-small-3.2-24b-instruct:free",
    ]
    
    @staticmethod
    async def _call_openrouter(model: str, image_bytes: bytes) -> dict | None:
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
                        logger.error(f"Model {model} failed with status {response.status}: {await response.text()}")
                        return None
            except Exception as e:
                logger.error(f"Exception calling {model}: {e}")
                return None

    @classmethod
    async def parse_receipt(cls, image_bytes: bytes) -> dict:
        for model in cls.MODELS:
            logger.info(f"Trying OCR model: {model}")
            result = await cls._call_openrouter(model, image_bytes)
            if result:
                return result
            logger.warning(f"Model {model} failed. Trying next...")
            
        raise Exception("All OCR models failed. Please try again later or check the logs.")
