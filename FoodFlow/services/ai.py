import aiohttp
import json
import logging
from FoodFlow.config import settings

logger = logging.getLogger(__name__)

class AIService:
    # List of text models for recipes
    MODELS = [
        "mistralai/mistral-small-3.2-24b-instruct:free", # Working & Smart
        "qwen/qwen3-30b-a3b:free",                        # Working & New
        "google/gemma-3-27b-it:free",                     # Good but unstable
        "deepseek/deepseek-chat-v3-0324:free",            # Good but unstable
        "openai/gpt-oss-20b:free"                         # Working fallback
    ]
    
    @classmethod
    async def generate_recipes(cls, ingredients: list[str]) -> dict | None:
        if not ingredients:
            return None
            
        ingredients_str = ", ".join(ingredients)
        
        prompt = (
            f"I have these ingredients: {ingredients_str}. "
            "Suggest 3 simple recipes I can cook using mostly these ingredients. "
            "For each recipe, provide a title, a short description, and estimated calories per serving. "
            "Respond ONLY in Russian language. "
            "Return ONLY a JSON object with this format: "
            "{\"recipes\": [{\"title\": \"...\", \"description\": \"...\", \"calories\": 500}]}"
        )

        for model in cls.MODELS:
            result = await cls._call_model(model, prompt)
            if result:
                return result
        
        return None

    @staticmethod
    async def _call_model(model: str, prompt: str) -> dict | None:
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
