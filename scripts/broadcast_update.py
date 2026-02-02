import asyncio
import logging
import sys
import os

# Add parent directory to path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiogram import Bot
from sqlalchemy import select
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from config import settings
from database.base import get_db
from database.models import User

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BROADCAST_MESSAGE = """
🚀 <b>Обновление FoodFlow!</b>

Мы добавили <b>умный калькулятор целей</b>! 🧠

Теперь не нужно гадать, сколько белков и углеводов тебе нужно:

1️⃣ Зайди в <b>Настройки ⚙️</b> -> <b>🎯 Изменить цели КБЖУ</b>
2️⃣ Бот сам рассчитает идеальную норму на основе твоего веса, возраста и цели
3️⃣ Ты можешь принять рекомендацию или задать свои калории — а БЖУ мы пересчитаем за тебя!

Настрой свои цели правильно и достигай результата быстрее! 💪
"""

async def main():
    bot = Bot(token=settings.BOT_TOKEN)
    
    logger.info("Starting broadcast...")
    
    users_count = 0
    success_count = 0
    block_count = 0
    
    async for session in get_db():
        # Get all users
        result = await session.execute(select(User.id))
        user_ids = result.scalars().all()
        
        users_count = len(user_ids)
        logger.info(f"Found {users_count} users.")
        
        for user_id in user_ids:
            try:
                await bot.send_message(user_id, BROADCAST_MESSAGE, parse_mode="HTML")
                success_count += 1
                logger.info(f"Sent to {user_id}")
                await asyncio.sleep(0.05) # Avoid flood limits
            except TelegramForbiddenError:
                logger.warning(f"User {user_id} blocked the bot.")
                block_count += 1
            except TelegramRetryAfter as e:
                logger.warning(f"Flood limit exceeded. Sleeping {e.retry_after}s")
                await asyncio.sleep(e.retry_after)
                # Retry once
                try:
                    await bot.send_message(user_id, BROADCAST_MESSAGE, parse_mode="HTML")
                    success_count += 1
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"Failed to send to {user_id}: {e}")
        
    logger.info(f"Broadcast finished. Total: {users_count}, Success: {success_count}, Blocked: {block_count}")
    await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
