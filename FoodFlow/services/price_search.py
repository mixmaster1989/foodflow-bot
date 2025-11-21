import aiohttp
import json
import logging
from FoodFlow.config import settings

logger = logging.getLogger(__name__)


class PriceSearchService:
    """Service to search for real-time prices using Perplexity Sonar"""
    MODEL = "perplexity/sonar"
    
    @staticmethod
    async def search_prices(product_name: str) -> dict | None:
        """
        Search for current prices of a product in Russian stores.
        Returns dict with prices from different stores or None if failed.
        """
        import re
        from datetime import datetime
        
        # Get current month and year
        current_date = datetime.now().strftime("%m.%Y")
        
        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://foodflow.app",
            "X-Title": "FoodFlow Bot"
        }
        
        prompt = (
            f"Найди актуальные цены на '{product_name}' в магазинах России "
            f"(Пятёрочка, Магнит, Лента, Перекрёсток) на {current_date}. "
            f"Верни ТОЛЬКО JSON (без markdown) в формате: "
            f"{{\"prices\": [{{\"store\": \"Название\", \"price\": 0.0}}]}}"
        )
        
        payload = {
            "model": PriceSearchService.MODEL,
            "messages": [{"role": "user", "content": prompt}]
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
                            
                            # Log full response for debugging
                            logger.info(f"Perplexity price search response for '{product_name}':\n{content}")
                            
                            # Try to extract JSON using regex
                            json_match = re.search(r'\{.*\}', content, re.DOTALL)
                            if json_match:
                                json_str = json_match.group(0)
                            else:
                                json_str = content.replace("```json", "").replace("```", "").strip()
                            
                            try:
                                data = json.loads(json_str)
                                prices = data.get("prices", [])
                                
                                if not prices:
                                    # If no prices found in JSON, maybe return raw text if it's informative?
                                    # But better to return None so we don't spam user with raw JSON.
                                    # Actually, if we have raw text that isn't JSON, we might want to show it.
                                    if not json_match and len(content) > 20:
                                         return {"raw_response": content}
                                    return None
                                
                                # Calculate stats
                                price_values = [p["price"] for p in prices if p.get("price")]
                                
                                return {
                                    "product": product_name,
                                    "prices": prices,
                                    "min_price": min(price_values) if price_values else None,
                                    "max_price": max(price_values) if price_values else None,
                                    "avg_price": sum(price_values) / len(price_values) if price_values else None
                                }
                            except json.JSONDecodeError:
                                # If JSON parsing fails, return raw content for debugging
                                logger.warning(f"Failed to parse JSON from Perplexity: {content}")
                                return {"raw_response": content}
                        
                        logger.warning(f"Price search (attempt {attempt+1}/3) failed: {response.status}")
                        if attempt < 2:
                            await asyncio.sleep(0.5)
                            continue
                except Exception as exc:
                    logger.error(f"Price search exception (attempt {attempt+1}/3): {exc}")
                    if attempt < 2:
                        await asyncio.sleep(0.5)
                        continue
        return None
