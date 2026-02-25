import asyncio
import logging
import sys
from pathlib import Path

# Add root directory to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from aiogram import Bot
from sqlalchemy import update
from sqlalchemy.future import select

from config import settings
from database.base import init_db, get_db
from database.models import User
from handlers.menu import show_main_menu

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TARGET_USER_ID = 911990304  # ElenaOdr

async def verify_target_user():
    bot = Bot(token=settings.BOT_TOKEN)
    await init_db()
    
    async for session in get_db():
        # Update user
        stmt = update(User).where(User.id == TARGET_USER_ID).values(is_verified=True)
        await session.execute(stmt)
        await session.commit()
        
        # Notify user
        try:
            # Send welcome message
            await bot.send_message(
                chat_id=TARGET_USER_ID,
                text="✅ <b>Доступ открыт!</b>\n\nИзвините за задержку. Бот теперь доступен для вас.\nНажмите /start или кнопку ниже для начала.",
                parse_mode="HTML"
            )
            logger.info(f"Verified and notified user {TARGET_USER_ID}")
        except Exception as e:
            logger.error(f"Failed to notify user {TARGET_USER_ID}: {e}")

    await bot.session.close()

if __name__ == "__main__":
    asyncio.run(verify_target_user())
