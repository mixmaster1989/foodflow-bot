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

HERBALIFE_MESSAGE = """
🌿 <b>Легенда вернулась: Кнопка Гербалайф снова в деле!</b>

Мы восстановили и прокачали поддержку продукции <b>Herbalife</b>. Теперь бот стал еще умнее:

✅ <b>Точный расчет:</b> Используем базу эксперта Herbalife. Порции в ложках, колпачках и штуках теперь считаются идеально.
✅ <b>Умное зрение:</b> Просто скинь фото банки или продукта — ИИ распознает его и предложит кнопку <code>🌿 Это Гербалайф</code>.
✅ <b>Голос и текст:</b> Скажи "Выпил Алоэ" или "Коктейль Ф1 Шоколад 2 ложки" — бот поймет тебя с полуслова.

<b>Как это работает?</b>
Если бот не уверен на 100%, он покажет меню выбора. Просто нажми <b>"🌿 Это Гербалайф"</b>, и расчет пойдет по экспертной базе.

Попробуй прямо сейчас! 🦾
"""

async def main():
    bot = Bot(token=settings.BOT_TOKEN)
    
    logger.info("Starting User notification (Herbalife)...")
    
    success_count = 0
    fail_count = 0
    
    async for session in get_db():
        result = await session.execute(select(User.id))
        user_ids = result.scalars().all()
        
        logger.info(f"Found {len(user_ids)} total users.")
        
        for user_id in user_ids:
            try:
                await bot.send_message(user_id, HERBALIFE_MESSAGE, parse_mode="HTML")
                success_count += 1
                logger.info(f"Sent to user {user_id}")
                await asyncio.sleep(0.05)
            except Exception as e:
                # logger.error(f"Failed to send to {user_id}: {e}") # Silent fails for normal users to avoid cluttering logs
                fail_count += 1
        
    logger.info(f"User Notification finished. Success: {success_count}, Failed: {fail_count}")
    await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
