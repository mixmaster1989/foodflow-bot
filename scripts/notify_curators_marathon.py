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

CURATOR_MESSAGE = """
👨‍🏫 <b>Вниманию Кураторов! Пришло время Марафонов!</b> 🏆

Мы официально запустили систему Марафонов. Твои новые возможности:

1️⃣ <b>Управление участниками:</b> Теперь ты можешь создавать марафоны и управлять ими.
2️⃣ <b>Инвайт-ссылки:</b> У каждого марафона есть секретный код. Просто скинь ссылку участнику, и он попадет в твою группу.
3️⃣ <b>Концепция Lite:</b> Мы упростили процесс входа — новички попадают в марафон мгновенно, без долгой регистрации.

Загляни в 👨‍🏫 <b>Кабинет Куратора</b> в главном меню, чтобы начать!

<i>Твой верный партнер по Марафонам, NeiroBot.</i> 🦾
"""

async def main():
    bot = Bot(token=settings.BOT_TOKEN)
    
    logger.info("Starting Curator notification...")
    
    success_count = 0
    fail_count = 0
    
    async for session in get_db():
        # Get all curators
        result = await session.execute(select(User.id).where(User.role == 'curator'))
        user_ids = result.scalars().all()
        
        logger.info(f"Found {len(user_ids)} curators.")
        
        for user_id in user_ids:
            try:
                await bot.send_message(user_id, CURATOR_MESSAGE, parse_mode="HTML")
                success_count += 1
                logger.info(f"Sent to curator {user_id}")
                await asyncio.sleep(0.05)
            except Exception as e:
                logger.error(f"Failed to send to {user_id}: {e}")
                fail_count += 1
        
    logger.info(f"Curator Notification finished. Success: {success_count}, Failed: {fail_count}")
    await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
