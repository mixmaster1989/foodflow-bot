import asyncio
import logging
import sys
from pathlib import Path

# Add root directory to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from aiogram import Bot
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from sqlalchemy.future import select

from config import settings
from database.base import init_db, get_db
from database.models import User

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def fix_keyboards():
    bot = Bot(token=settings.BOT_TOKEN)
    await init_db()
    
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🏠 Главное меню")]],
        resize_keyboard=True,
        persistent=True
    )
    
    logger.info("Starting keyboard distribution...")
    
    count = 0
    async for session in get_db():
        stmt = select(User).where(User.is_verified == True)
        result = await session.execute(stmt)
        users = result.scalars().all()
        
        for user in users:
            try:
                # Send a silent message just to update the keyboard
                # Or a useful tip
                await bot.send_message(
                    chat_id=user.id,
                    text="🔄 Обновление интерфейса: добавлена кнопка меню.",
                    reply_markup=kb
                )
                count += 1
                logger.info(f"Updated user {user.id}")
                await asyncio.sleep(0.1) 
            except Exception as e:
                logger.error(f"Failed to update user {user.id}: {e}")

    await bot.session.close()
    logger.info(f"Finished. Updated {count} users.")

if __name__ == "__main__":
    asyncio.run(fix_keyboards())
