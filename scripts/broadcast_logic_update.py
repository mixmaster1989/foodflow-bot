#!/usr/bin/env python3
import asyncio
import logging
import sys
from pathlib import Path

# Add root directory to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from sqlalchemy import select

from config import settings
from database.base import get_db, init_db
from database.models import User

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
DRY_RUN = False  # Set to False to actually send messages
TEST_MODE = False # Set to True to send only to specific test IDs
TEST_USER_IDS = [432823154] 

USER_MESSAGE = """🍎 <b>FoodFlow стал еще умнее: Большое обновление логики!</b>

Технические работы официально завершены, спасибо всем за терпение! Мы внимательно слушали ваши отзывы и внесли несколько важных улучшений, которые сделают ведение дневника намного удобнее:

✅ <b>Понимаем кулинарный контекст</b>
Теперь бот научился отличать «продуктовую корзину» от «готового блюда». Если вы пишете «салат из огурцов и помидоров» — ИИ поймет, что это одно блюдо, и не будет дробить его на отдельные овощи. Он стал лучше чувствовать разницу между списком покупок и тем, что реально лежит в вашей тарелке.

✅ <b>Полный контроль в ваших руках</b>
Если ИИ всё-таки ошибся (например, посчитал «кофе и круассан» одним блюдом, а вы хотите записать их отдельно) — теперь под сообщением есть кнопки <b>«Разделить»</b> или <b>«Это одно блюдо»</b>. Одно нажатие, и бот мгновенно пересчитает всё правильно именно в том режиме, который вам нужен!

✅ <b>Тотальное редактирование (по вашей просьбе!)</b>
Теперь при вводе списка продуктов вы можете редактировать КБЖУ для <b>каждой позиции отдельно</b>. Нажали «Редактировать» → Выбрали продукт → Изменили калории или белки. Бот тут же сам пересчитает общий итог для всего приема пищи. Максимальная точность там, где она нужна!

Мы продолжаем работать над тем, чтобы FoodFlow стал вашим самым удобным помощником. Еще раз спасибо, что остаетесь с нами! 🚀"""

async def send_msg(bot, user_id, text):
    if DRY_RUN:
        logger.info(f"[DRY RUN] Would send to {user_id}")
        return True

    try:
        await bot.send_message(user_id, text, parse_mode="HTML")
        return True
    except TelegramForbiddenError:
        logger.warning(f"User {user_id} blocked the bot.")
        return False
    except TelegramRetryAfter as e:
        logger.warning(f"Flood limit exceeded. Sleeping {e.retry_after}s")
        await asyncio.sleep(e.retry_after)
        return await send_msg(bot, user_id, text) # Retry once
    except Exception as e:
        logger.error(f"Failed to send to {user_id}: {e}")
        return False

async def main():
    bot = Bot(token=settings.BOT_TOKEN)
    await init_db()

    logger.info(f"Starting broadcast (DRY_RUN={DRY_RUN}, TEST_MODE={TEST_MODE})...")

    stats = {"total": 0, "success": 0, "blocked": 0, "failed": 0}

    async for session in get_db():
        stmt = select(User)
        if TEST_MODE:
            stmt = stmt.where(User.id.in_(TEST_USER_IDS))

        result = await session.execute(stmt)
        users = result.scalars().all()
        stats["total"] = len(users)

        for user in users:
            if await send_msg(bot, user.id, USER_MESSAGE):
                stats["success"] += 1
            else:
                stats["blocked"] += 1 # Simplified check

            await asyncio.sleep(0.05) # Rate limit protection

    logger.info(f"Finished. Stats: {stats}")
    await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
