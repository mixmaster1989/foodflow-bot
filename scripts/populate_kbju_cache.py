"""
Универсальный скрипт-конвейер для пакетного заполнения каноничного кэша КБЖУ.
Использование: Заполнить массив BATCH_DATA и запустить скрипт.
"""
import asyncio
import logging
import sys

sys.path.append('.')

from sqlalchemy import select
from database.base import Base, engine, async_session
from database.models import CanonicalProduct

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────
# BATCH DATA: (base_name, display_name, cal, prot, fat, carbs, fiber)
# Все значения строго на 100 грамм готового/сырого продукта.
# Источник: Судья (AI Agent) на основе USDA, таблиц Скурихина, этикеток.
# ──────────────────────────────────────────────────────────

BATCH_DATA = [
    # ── Пачка 4 (позиции 41-50 + фикс «гречка отварная») ──
    ("Капуста квашеная",    "Капуста квашеная",                              19,  1.8,  0.1,  2.2,  2.0),
    ("Борщ",                "Борщ домашний (со свеклой и мясом)",             49,  2.8,  1.3,  6.7,  1.0),
    ("Батончик Гербалайф",  "Formula 1 Express Bar (батончик)",             410, 28.0, 14.0, 42.0,  6.0),
    ("Солянка",             "Солянка мясная сборная",                         64,  4.5,  3.5,  3.8,  0.5),
    ("Протеиновый коктейль","Протеиновый коктейль (готовый на молоке 1.5%)",  79,  6.5,  1.5, 10.0,  1.8),
    ("Майонез",             "Майонез классический 67%",                      624,  0.3, 67.0,  3.7,  0.0),
    ("Купаты куриные",      "Купаты куриные (жареные)",                     185, 17.0, 12.0,  2.0,  0.0),
    ("Индейка",             "Индейка (филе варёное)",                        130, 25.0,  3.2,  0.0,  0.0),
    ("яблоко",              "Яблоко свежее",                                 52,  0.3,  0.2, 13.8,  2.4),
    ("Гречка отварная",     "Гречка отварная",                              110,  4.2,  1.1, 21.3,  3.7),
]


async def populate_batch():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    added = 0
    skipped = 0

    async with async_session() as db:
        for item in BATCH_DATA:
            raw_name, display, cal, prot, fat, carbs, fiber = item
            base = raw_name.strip().lower()

            # Проверяем — уже есть в кэше?
            stmt = select(CanonicalProduct).where(CanonicalProduct.base_name == base)
            existing = (await db.execute(stmt)).scalar_one_or_none()

            if existing and existing.is_verified:
                logger.info(f"⏭️  SKIP (уже verified): {base}")
                skipped += 1
                continue

            if existing:
                # Обновляем неверифицированную запись
                existing.display_name = display
                existing.calories = cal
                existing.protein = prot
                existing.fat = fat
                existing.carbs = carbs
                existing.fiber = fiber
                existing.source = "ai_human_judge"
                existing.is_verified = True
                logger.info(f"🔄  UPDATE → verified: {base} ({cal} kcal)")
            else:
                new_prod = CanonicalProduct(
                    base_name=base,
                    display_name=display,
                    calories=cal,
                    protein=prot,
                    fat=fat,
                    carbs=carbs,
                    fiber=fiber,
                    source="ai_human_judge",
                    is_verified=True
                )
                db.add(new_prod)
                logger.info(f"✅  ADD: {base} ({cal} kcal)")

            added += 1

        await db.commit()

    logger.info(f"\n{'='*50}")
    logger.info(f"Добавлено/обновлено: {added}, Пропущено: {skipped}")
    logger.info(f"{'='*50}")

    # Отчёт: все текущие записи в кэше
    async with async_session() as db:
        stmt = select(CanonicalProduct).order_by(CanonicalProduct.id)
        result = (await db.execute(stmt)).scalars().all()
        logger.info(f"\n📊 Всего в canonical_products: {len(result)} записей")
        for p in result:
            v = "✅" if p.is_verified else "❌"
            # Проверка: макросы сходятся с калориями?
            expected = p.protein * 4 + p.fat * 9 + p.carbs * 4
            diff = abs(p.calories - expected) / max(p.calories, 1) * 100
            math_ok = "📐" if diff < 20 else "⚠️"
            logger.info(f"  {v} {math_ok} {p.base_name}: {p.calories} kcal ({p.protein}Б/{p.fat}Ж/{p.carbs}У)")


if __name__ == "__main__":
    asyncio.run(populate_batch())
