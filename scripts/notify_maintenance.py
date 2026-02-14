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

MAINTENANCE_MESSAGE = """
✅ <b>Технические работы завершены!</b>

Бот снова работает в штатном режиме. 🚀
Спасибо за ожидание!
"""

async def main():
    bot = Bot(token=settings.BOT_TOKEN)
    
    logger.info("Starting maintenance broadcast...")
    
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
                await bot.send_message(user_id, MAINTENANCE_MESSAGE, parse_mode="HTML")
                success_count += 1
                if i % 10 == 0:
                    logger.info(f"Sent: {i}/{total_users}")
                await asyncio.sleep(0.05) # 20 messages per second limit
            except TelegramForbiddenError:
                block_count += 1
            except TelegramRetryAfter as e:
                logger.warning(f"Flood limit! Sleeping {e.retry_after}s")
                await asyncio.sleep(e.retry_after)
                # Retry once
                try:
                    await bot.send_message(user_id, MAINTENANCE_MESSAGE, parse_mode="HTML")
                    success_count += 1
                except:
                    fail_count += 1
            except Exception as e:
                logger.error(f"Failed to send to {user_id}: {e}")
                fail_count += 1
        
    logger.info(f"Broadcast finished. Success: {success_count}, Blocked: {block_count}, Failed: {fail_count}")
    await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
