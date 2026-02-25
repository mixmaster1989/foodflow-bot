import asyncio
import logging
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from sqlalchemy import select

from config import settings
from database.base import get_db
from database.models import User

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BROADCAST_MESSAGE = """
🛠 <b>Обновление интерфейса</b>

Друзья, мы улучшили работу бота! 🚀
Если у вас вдруг пропала кнопка <b>«🏠 Главное меню»</b> внизу экрана — не волнуйтесь.

Чтобы вернуть её на место, просто нажмите на команду:
👉 /start

И меню появится снова! ✨
Спасибо, что вы с нами! 💚
"""

async def main():
    bot = Bot(token=settings.BOT_TOKEN)

    logger.info("Starting menu fix broadcast...")

    success_count = 0
    fail_count = 0
    block_count = 0

    async for session in get_db():
        # Get all users
        result = await session.execute(select(User.id))
        user_ids = result.scalars().all()

        total_users = len(user_ids)
        logger.info(f"Found {total_users} users to notify.")

        for i, user_id in enumerate(user_ids):
            try:
                await bot.send_message(user_id, BROADCAST_MESSAGE, parse_mode="HTML")
                success_count += 1
                if i % 10 == 0:
                    logger.info(f"Sent: {i}/{total_users}")
                await asyncio.sleep(0.05) # 20 messages per second limit
            except TelegramForbiddenError:
                block_count += 1
                logger.debug(f"User {user_id} blocked the bot.")
            except TelegramRetryAfter as e:
                logger.warning(f"Flood limit! Sleeping {e.retry_after}s")
                await asyncio.sleep(e.retry_after) # Retry once
                try:
                    await bot.send_message(user_id, BROADCAST_MESSAGE, parse_mode="HTML")
                    success_count += 1
                except Exception:
                    fail_count += 1
            except Exception as e:
                logger.error(f"Failed to send to {user_id}: {e}")
                fail_count += 1

    logger.info(f"Broadcast finished. Success: {success_count}, Blocked: {block_count}, Failed: {fail_count}")
    await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
