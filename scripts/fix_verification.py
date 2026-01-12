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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CORRECT_USER_ID = 7846721167
WRONG_USER_ID = 911990304 # ElenaOdr

async def fix_verification():
    bot = Bot(token=settings.BOT_TOKEN)
    await init_db()
    
    async for session in get_db():
        # 1. Verify Wife
        logger.info(f"Verifying user {CORRECT_USER_ID}...")
        stmt_verify = update(User).where(User.id == CORRECT_USER_ID).values(is_verified=True)
        await session.execute(stmt_verify)
        
        # 2. Unverify Wrong User
        logger.info(f"Unverifying user {WRONG_USER_ID}...")
        stmt_unverify = update(User).where(User.id == WRONG_USER_ID).values(is_verified=False)
        await session.execute(stmt_unverify)
        
        await session.commit()
        
        # 3. Send Message to Wife
        try:
            await bot.send_message(
                chat_id=CORRECT_USER_ID,
                text="сама ты хуй, мать!))) 😹\n\n(Доступ открыт, пользуйся)",
                parse_mode="HTML"
            )
            logger.info(f"Message sent to {CORRECT_USER_ID}")
        except Exception as e:
            logger.error(f"Failed to send message: {e}")

    await bot.session.close()

if __name__ == "__main__":
    asyncio.run(fix_verification())
