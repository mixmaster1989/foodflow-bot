
import json
import logging
import aiohttp
import asyncio
from typing import List, Dict
from config import settings

logger = logging.getLogger("ai.brain")

class AIBrainService:
    """Core AI Brain Service for semantic understanding of user input."""

    MODEL = "google/gemini-2.5-flash-lite" # Fast, Smart enough

    SYSTEM_PROMPT = """
Ты — Мозг бота FoodFlow. Твоя задача — понять намерение пользователя и извлечь данные.
Доступные намерения (intents):
1. 'log_consumption' — пользователь ЯВНО указал, что СЪЕЛ ("Съел яблоко", "На завтрак кофе", "Выпил чай", "Ужин: макароны").
2. 'add_to_fridge' — пользователь ЯВНО указал, что КУПИЛ или хочет ДОБАВИТЬ ("Купил молока", "В холодильник сыр", "+ банан").
3. 'unknown' — если нет явного глагола действия или контекста (просто название продукта: "Банан", "Молоко").

Твоя задача — вернуть JSON объект:
{
  "intent": "log_consumption" | "add_to_fridge" | "unknown",
  "product": "Название продукта" (или null),
  "weight": 100 (число в граммах, или null если не указано),
  "quantity": 1 (число штук, если указано, иначе 1),
  "original_text": "исходный текст"
}

Правила экстракции:
- Если пользователь говорит "два яблока", quantity=2, weight=null (если вес не назван явно).
- Если "яблоко 200г", product="яблоко", weight=200.
- Если "полкило", weight=500.
- СТРОГО: Если просто "Яблоко" (без "съел", "купил") -> intent="unknown".
- СТРОГО: Если Гербалайф ("Коктейль Ф1", "Алоэ") без глагола -> intent="unknown".

НЕ ПИШИ НИЧЕГО КРОМЕ JSON.
"""

    @classmethod
    async def analyze_text(cls, text: str) -> dict | None:
        """Call LLM to analyze text and return structured data."""
        
        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://foodflow.app",
            "X-Title": "FoodFlow Bot",
        }

        payload = {
            "model": cls.MODEL,
            "messages": [
                {"role": "system", "content": cls.SYSTEM_PROMPT},
                {"role": "user", "content": text}
            ],
            "response_format": {"type": "json_object"}
        }

        for attempt in range(2):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers=headers,
                        json=payload,
                        timeout=10
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            content = data['choices'][0]['message']['content']
                            # Clean output just in case
                            content = content.replace("```json", "").replace("```", "").strip()
                            return json.loads(content)
                        else:
                            logger.warning(f"AI Brain error {response.status}: {await response.text()}")
            except Exception as e:
                logger.error(f"AI Brain exception: {e}")
                
            await asyncio.sleep(0.5)
            
        return None

    @classmethod
    async def resolve_herbalife_product(cls, text: str, products_context: List[Dict]) -> str | None:
        """Use AI to match user input to a specific Herbalife Product ID."""
        
        # Prepare a compact list of products for the prompt
        compact_list = [
            {"id": p["id"], "name": p["name"], "aliases": p.get("aliases", [])}
            for p in products_context
        ]

        prompt = f"""
Ты — эксперт по продукции Herbalife. Твоя задача — сопоставить ввод пользователя с конкретным ID продукта из предоставленного списка.
Если во вводе указан вкус (например, 'дыня', 'манго', 'шоколад'), обязательно выбери соответствующий ID.

Список продуктов:
{json.dumps(compact_list, ensure_ascii=False, indent=2)}

Ввод пользователя: "{text}"

Твоя задача — вернуть JSON:
{{
  "matched_product_id": "id_from_list" (или null если нет совпадения),
  "reason": "краткое объяснение почему выбран этот ID"
}}
"""

        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://foodflow.app",
            "X-Title": "FoodFlow Bot",
        }

        payload = {
            "model": cls.MODEL,
            "messages": [
                {"role": "system", "content": "Return ONLY JSON."},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"}
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=10
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        content = data['choices'][0]['message']['content']
                        logger.info(f"Herbalife AI Raw Response: {content[:200]}")
                        result = json.loads(content)
                        matched_id = result.get("matched_product_id")
                        logger.info(f"Herbalife AI Matched ID: {matched_id}, Reason: {result.get('reason', 'N/A')}")
                        return matched_id
                    else:
                        logger.warning(f"Herbalife AI HTTP Error: {response.status}")
        except Exception as e:
            logger.error(f"Herbalife Resolution AI Error: {e}")
            

    @classmethod
    async def analyze_image(cls, message_or_path: any, prompt: str = "Describe this image.") -> str | None:
        """Analyze image using Vision model. Accepts aiogram Message or file path."""
        import base64
        import os
        
        # Determine image source
        b64_image = None
        
        try:
            if isinstance(message_or_path, str):
                # It's a file path
                with open(message_or_path, "rb") as image_file:
                    b64_image = base64.b64encode(image_file.read()).decode('utf-8')
            else:
                # Assume it's an aiogram Message object
                # We need to download it first. This requires the 'bot' instance.
                # Since we don't have easy access to bot instance here without circular imports,
                # we'll assume the caller handles downloading if it's complex.
                # BUT, wait! We can get bot from message.bot
                bot = message_or_path.bot
                if message_or_path.photo:
                    file_id = message_or_path.photo[-1].file_id
                    file = await bot.get_file(file_id)
                    file_path = file.file_path
                    
                    # Download to memory
                    io_obj = await bot.download_file(file_path)
                    b64_image = base64.b64encode(io_obj.read()).decode('utf-8')

            if not b64_image:
                logger.error("Could not obtain base64 image data")
                return None

            headers = {
                "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://foodflow.app",
                "X-Title": "FoodFlow Bot",
            }

            payload = {
                "model": "google/gemini-2.0-flash-exp:free", # Using Free/Exp model for Vision
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{b64_image}"
                                }
                            }
                        ]
                    }
                ]
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=20
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        content = data['choices'][0]['message']['content']
                        logger.info(f"Vision Analysis: {content[:100]}...")
                        return content
                    else:
                        logger.warning(f"Vision API Error: {response.status} - {await response.text()}")
                        
        except Exception as e:
            logger.error(f"Vision Analysis Exception: {e}", exc_info=True)
            
        return None
