"""Backfill fiber data for existing products.

This script:
1. Finds all products with fiber = 0 or NULL
2. Asks AI to estimate fiber content based on product name
3. Updates the database

Run: PYTHONPATH=. python3 scripts/backfill_fiber.py
"""
import asyncio
import json
import logging
import aiohttp
from sqlalchemy import select, or_

from config import settings
from database.base import async_session
from database.models import Product, ConsumptionLog

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def estimate_fiber(product_name: str) -> float:
    """Ask AI to estimate fiber content for a product."""
    prompt = (
        f"Сколько клетчатки (fiber) в граммах содержится в 100г продукта '{product_name}'?\n"
        "Ответь ТОЛЬКО числом (например: 2.4). Если клетчатки нет (мясо, масло, сахар) — ответь 0."
    )
    
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": "openai/gpt-4.1-mini",  # Fast and cheap
        "messages": [{"role": "user", "content": prompt}]
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=15
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    content = result["choices"][0]["message"]["content"].strip()
                    # Parse number from response
                    content = content.replace(",", ".").replace("г", "").replace("g", "").strip()
                    return float(content)
    except Exception as e:
        logger.error(f"Error estimating fiber for '{product_name}': {e}")
    
    return 0.0


async def backfill_products():
    """Update all products with missing fiber data."""
    async with async_session() as session:
        # Find products with no fiber
        stmt = select(Product).where(
            or_(Product.fiber == 0, Product.fiber == None)
        )
        result = await session.execute(stmt)
        products = result.scalars().all()
        
        logger.info(f"Found {len(products)} products with no fiber data.")
        
        updated = 0
        for product in products:
            fiber = await estimate_fiber(product.name)
            if fiber > 0:
                product.fiber = fiber
                updated += 1
                logger.info(f"✅ {product.name}: {fiber}г клетчатки")
            else:
                logger.info(f"⏭️ {product.name}: 0г (ожидаемо)")
            
            # Rate limiting: 0.5s between requests
            await asyncio.sleep(0.5)
        
        await session.commit()
        logger.info(f"Updated {updated} products with fiber data.")


async def backfill_consumption_logs():
    """Update consumption logs with missing fiber data."""
    async with async_session() as session:
        stmt = select(ConsumptionLog).where(
            or_(ConsumptionLog.fiber == 0, ConsumptionLog.fiber == None)
        )
        result = await session.execute(stmt)
        logs = result.scalars().all()
        
        logger.info(f"Found {len(logs)} consumption logs with no fiber data.")
        
        updated = 0
        for log in logs:
            fiber_per_100g = await estimate_fiber(log.product_name)
            if fiber_per_100g > 0:
                # Estimate consumed fiber based on calories ratio
                # Assume average: 200 kcal = 100g portion
                if log.calories and log.calories > 0:
                    estimated_portion_g = (log.calories / 200) * 100  # rough estimate
                    log.fiber = (estimated_portion_g / 100) * fiber_per_100g
                else:
                    log.fiber = fiber_per_100g  # Default to 100g portion
                updated += 1
                logger.info(f"✅ Log: {log.product_name}: ~{log.fiber:.1f}г клетчатки")
            
            await asyncio.sleep(0.5)
        
        await session.commit()
        logger.info(f"Updated {updated} consumption logs with fiber data.")


async def main():
    logger.info("=== Starting Fiber Backfill ===")
    await backfill_products()
    await backfill_consumption_logs()
    logger.info("=== Fiber Backfill Complete ===")


if __name__ == "__main__":
    asyncio.run(main())
