import aiohttp
import json
import logging
from FoodFlow.config import settings

logger = logging.getLogger(__name__)

class NormalizationService:
    # Using Perplexity Sonar for fast, web-augmented normalization
    MODEL = "perplexity/sonar" 
    
    @staticmethod
    async def normalize_products(raw_items: list[dict]) -> list[dict]:
        """
        Takes a list of raw items (dict with 'name', 'price', 'quantity').
        Returns a list of normalized items with 'name', 'category', 'calories'.
        """
        if not raw_items:
            return []
            
        # Prepare the list for the prompt
        items_str = "\n".join([f"- {item.get('name', 'Unknown')}" for item in raw_items])
        
        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://foodflow.app",
            "X-Title": "FoodFlow Bot"
        }
        
        prompt = (
            "You are a smart receipt assistant. I have a list of raw product names from a Russian grocery receipt. "
            "Many names are abbreviated or contain OCR errors (e.g., 'СЕЛЬКИ насло' -> 'Масло подсолнечное', 'Шинка ВЕЛОСИПЕД' -> 'Ветчина'). "
            "Your task:\n"
            "1. Identify the real product name using web search if needed.\n"
            "2. PRESERVE brand names if recognizable (e.g., 'МИЛКА' -> 'Милка', 'Lays' -> 'Lays').\n"
            "3. PRESERVE weight/volume if present (e.g., '450г', '1л', '200мл').\n"
            "4. Categorize it (e.g., Молочные продукты, Мясо, Овощи, Снеки, Бакалея).\n"
            "5. Estimate calories per 100g.\n"
            "6. Return a JSON object with a list of normalized items. Keep the original order.\n"
            "IMPORTANT: All names and categories MUST be in RUSSIAN language.\n\n"
            "Input List:\n"
            f"{items_str}\n\n"
            "Output Format (JSON ONLY):\n"
            "{\"normalized\": [{\"original\": \"...\", \"name\": \"Название с брендом и весом (RU)\", \"category\": \"Категория (RU)\", \"calories\": 123}]}"
        )
        
        payload = {
            "model": NormalizationService.MODEL,
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
                    timeout=60
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        content = result['choices'][0]['message']['content']
                        # Clean markdown
                        content = content.replace("```json", "").replace("```", "").strip()
                        
                        try:
                            parsed = json.loads(content)
                            normalized_map = {item['original']: item for item in parsed.get('normalized', [])}
                            
                            # Merge back with original data (price, quantity)
                            final_items = []
                            for item in raw_items:
                                raw_name = item.get('name', 'Unknown')
                                norm_data = normalized_map.get(raw_name, {})
                                
                                final_items.append({
                                    "name": norm_data.get('name', raw_name), # Fallback to raw
                                    "price": item.get('price', 0.0),
                                    "quantity": item.get('quantity', 1.0),
                                    "category": norm_data.get('category', 'Uncategorized'),
                                    "calories": norm_data.get('calories', 0)
                                })
                            return final_items
                            
                        except json.JSONDecodeError:
                            logger.error(f"Failed to parse Normalization JSON: {content}")
                            return raw_items # Fallback
                    else:
                        logger.error(f"Normalization API failed: {await response.text()}")
                        return raw_items
            except Exception as e:
                logger.error(f"Exception in Normalization Service: {e}")
                return raw_items
