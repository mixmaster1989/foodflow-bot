import asyncio
import logging
import sys

sys.path.append('.')

from sqlalchemy import select, text
from database.base import Base, engine, async_session
from database.models import CanonicalProduct

logging.basicConfig(level=logging.INFO)

async def populate_top10():
    # Роль Судьи (human/expert reasoning). 
    # Жестко выверенные данные на 100 грамм:
    # 1. Банан (USDA) - 89 kcal
    # 2. Яблоко (USDA) - 52 kcal
    # 3. Молоко 3.2% - 60 kcal
    # 4. Кофе с молоком (50% кофе, 50% молока 3.2%) - 30 kcal
    # 5. Сметана 15% - 158 kcal
    # 6. Огурец - 15 kcal
    # 7. Салат (помидоры 45%, огурцы 45%, масло 10%) - 106 kcal
    # 8. Коктейль Гербалайф (готовый на молоке 1.5%) - 79 kcal (из расчета ~220ккал на порцию 276г)
    # 9. f1_vanilla (сухой порошок Формула 1) - 365 kcal
    # 10. Чай Гербалайф (готовый напиток) - 2 kcal
    judgement = [
        ("банан", "Банан свежий", 89.0, 1.1, 0.3, 22.8, 2.6),
        ("яблоко", "Яблоко свежее", 52.0, 0.3, 0.2, 13.8, 2.4),
        ("молоко", "Молоко коровье 3.2%", 60.0, 3.0, 3.2, 4.7, 0.0),
        ("кофе с молоком", "Кофе с молоком (готовый)", 30.0, 1.5, 1.6, 2.4, 0.0),
        ("сметана", "Сметана 15%", 158.0, 2.6, 15.0, 3.0, 0.0),
        ("огурец", "Огурец свежий", 15.0, 0.6, 0.1, 3.6, 0.5),
        ("салат", "Салат овощной с маслом", 106.0, 0.8, 10.0, 3.5, 1.2),
        ("коктейль гербалайф", "Коктейль Формула 1 (на молоке 1.5%)", 79.0, 6.5, 1.5, 10.0, 1.8),
        ("f1_vanilla", "Формула 1 Ваниль (сухой порошок)", 365.0, 35.0, 8.5, 35.0, 9.6),
        ("чай гербалайф", "Травяной напиток Термоджетикс (готовый)", 2.0, 0.1, 0.0, 0.4, 0.0)
    ]

    async with async_session() as db:
        for item in judgement:
            bn, dn, c, p, f, carbs, fib = item
            
            stmt = select(CanonicalProduct).where(CanonicalProduct.base_name == bn)
            existing = (await db.execute(stmt)).scalar_one_or_none()
            
            if existing:
                existing.calories = c
                existing.protein = p
                existing.fat = f
                existing.carbs = carbs
                existing.fiber = fib
                existing.display_name = dn
                existing.source = "ai_human_judge"
            else:
                new_prod = CanonicalProduct(
                    base_name=bn,
                    display_name=dn,
                    calories=c,
                    protein=p,
                    fat=f,
                    carbs=carbs,
                    fiber=fib,
                    source="ai_human_judge",
                )
                db.add(new_prod)
        
        await db.commit()
        logging.info("Top 10 items added/updated to CanonicalProduct cache.")

        # Устанавливаем флаг верификации через чистый SQL (так как добавили колонку через ALTER TABLE)
        await db.execute(text("UPDATE canonical_products SET is_verified = 1 WHERE source = 'ai_human_judge'"))
        await db.commit()
        logging.info("Set is_verified=1 for all top 10 products.")

if __name__ == "__main__":
    asyncio.run(populate_top10())
