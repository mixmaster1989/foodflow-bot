import asyncio
import logging
import sys
from pathlib import Path

# Add root directory to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from aiogram import Bot
from sqlalchemy.future import select

from config import settings
from database.base import get_db, init_db
from database.models import User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def notify_update():
    bot = Bot(token=settings.BOT_TOKEN)
    await init_db()

    msg_text = (
        "🚀 <b>Обновление FoodFlow!</b>\n\n"
        "Мы обновили меню холодильника:\n"
        "1️⃣ Кнопка <b>«Список покупок» скрыта</b> (пока не требуется).\n"
        "2️⃣ Добавлена кнопка <b>«➕ Добавить еду»</b> в меню холодильника.\n\n"
        "Теперь вы можете быстро добавлять:\n"
        "• 📄 <b>Чеки</b> (как раньше)\n"
        "• 🏷️ <b>Продукты</b> (по фото этикетки или самого продукта)\n"
        "• 🥘 <b>Готовые блюда</b> (по фото тарелки)\n\n"
        "Попробуйте прямо сейчас!"
    )

    count = 0
    async for session in get_db():
        stmt = select(User).where(User.is_verified)
        result = await session.execute(stmt)
        users = result.scalars().all()

        for user in users:
            try:
                await bot.send_message(chat_id=user.id, text=msg_text, parse_mode="HTML")
                count += 1
                logger.info(f"Notified user {user.id}")
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Failed to notify user {user.id}: {e}")

    await bot.session.close()
    logger.info(f"Notification sent to {count} users.")

if __name__ == "__main__":
    asyncio.run(notify_update())
