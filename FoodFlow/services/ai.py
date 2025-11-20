import aiohttp
import json
import logging
from FoodFlow.config import settings

logger = logging.getLogger(__name__)

class AIService:
    MODEL = "google/gemma-3-27b-it:free" # Fast and smart enough for recipes
    
    @staticmethod
    async def generate_recipes(ingredients: list[str]) -> dict | None:
        if not ingredients:
            return None
            
        ingredients_str = ", ".join(ingredients)
        
        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://foodflow.app",
            "X-Title": "FoodFlow Bot"
        }
        
        prompt = (
            f"I have these ingredients: {ingredients_str}. "
            "Suggest 3 simple recipes I can cook using mostly these ingredients. "
            "For each recipe, provide a title, a short description, and estimated calories per serving. "
            "Respond ONLY in Russian language. "
            "Return ONLY a JSON object with this format: "
            "{\"recipes\": [{\"title\": \"...\", \"description\": \"...\", \"calories\": 500}]}"
        )
        
        payload = {
            "model": AIService.MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }
        
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
                        logger.error(f"AI Recipe generation failed: {await response.text()}")
                        return None
            except Exception as e:
                logger.error(f"Exception in AI Service: {e}")
                return None
