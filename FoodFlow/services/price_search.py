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
        
        Example return:
        {
            "product": "Сахар 1кг",
            "prices": [
                {"store": "Пятёрочка", "price": 52.99},
                {"store": "Магнит", "price": 59.99},
                {"store": "Лента", "price": 79.99}
            ],
            "min_price": 52.99,
            "max_price": 79.99,
            "avg_price": 64.32
        }
        """
        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://foodflow.app",
            "X-Title": "FoodFlow Bot"
        }
        
        prompt = (
            f"Найди актуальные цены на '{product_name}' в магазинах России "
            f"(Пятёрочка, Магнит, Лента, Перекрёсток) на ноябрь 2025. "
            f"Верни ТОЛЬКО JSON (без markdown) в формате: "
            f"{{\"prices\": [{{\"store\": \"Название\", \"price\": 0.0}}]}}"
        )
        
        payload = {
            "model": PriceSearchService.MODEL,
            "messages": [{"role": "user", "content": prompt}]
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
                        
                        # Try to extract JSON from response
                        content = content.replace("```json", "").replace("```", "").strip()
                        
                        try:
                            data = json.loads(content)
                            prices = data.get("prices", [])
                            
                            if not prices:
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
                    
                    logger.error(f"Price search failed: {await response.text()}")
                    return None
            except Exception as exc:
                logger.error(f"Price search exception: {exc}")
                return None
