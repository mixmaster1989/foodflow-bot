import asyncio
import logging
import sys
from pathlib import Path

# Add root directory to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from aiogram import Bot
from sqlalchemy.future import select

from config import settings
from database.base import init_db, get_db
from database.models import User
from handlers.menu import show_main_menu

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TARGET_USER_ID = 7846721167

async def create_verify_user():
    bot = Bot(token=settings.BOT_TOKEN)
    await init_db()
    
    async for session in get_db():
        # Check if exists
        stmt = select(User).where(User.id == TARGET_USER_ID)
        user = (await session.execute(stmt)).scalar_one_or_none()
        
        if not user:
            logger.info("User not found. Creating new verified user...")
            # We don't know the username, so we'll set it to None or a placeholder
            user = User(
                id=TARGET_USER_ID, 
                username="Wife_Manually_Added", 
                is_verified=True
            )
            session.add(user)
        else:
            logger.info("User exists. Updating verification...")
            user.is_verified = True
        
        await session.commit()
        logger.info(f"User {TARGET_USER_ID} verified in DB.")
        
        # Send Menu to force update state
        try:
             # Just send a simple text to prompt command
             await bot.send_message(
                chat_id=TARGET_USER_ID,
                text="🚀 <b>Всё, починил!</b>\n\nЯ тебя в базу внес вручную. Теперь нажми /start или кнопку меню.",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Failed to send message: {e}")

    await bot.session.close()

if __name__ == "__main__":
    asyncio.run(create_verify_user())
