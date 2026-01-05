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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def notify_testers():
    bot = Bot(token=settings.BOT_TOKEN)
    await init_db()
    
    msg_text = (
        "🛠️ <b>Важный Патч (v1.2): Холодильник и Логирование</b>\n\n"
        "Мы обновили бота. Список изменений:\n\n"
        "1️⃣ <b>Кнопка «➕ Добавить еду» в Холодильнике</b>\n"
        "Теперь можно добавлять продукты не только чеком, но и вручную:\n"
        "- <i>Этикетка/Продукт</i>: Сфоткайте продукт -> Бот добавит его.\n"
        "- <i>Готовое блюдо</i>: Сфоткайте тарелку -> Бот добавит как продукт.\n\n"
        "2️⃣ <b>Логирование съеденного («Я это съел»)</b>\n"
        "При отправке фото блюда в чат теперь:\n"
        "- Бот спросит <b>вес порции</b> (в граммах).\n"
        "- Если весов нет — можно нажать <b>«🚫 Нет весов»</b> (бот запишет стандартную порцию ~300г).\n"
        "- КБЖУ пересчитывается автоматически под вес.\n\n"
        "3️⃣ <b>Интерфейс</b>\n"
        "- Убрана кнопка «Список покупок» (временно).\n"
        "- Убрана кнопка «Совет AI» (из-за сбоев).\n\n"
        "🧪 <b>Как тестировать:</b>\n"
        "1. Зайдите в 🧊 <b>Холодильник</b> -> Нажмите «➕ Добавить еду» -> Попробуйте разные способы (Чек/Этикетка).\n"
        "2. Просто пришлите боту фото любой еды -> Нажмите «🍽️ Я это съел» -> Введите вес или выберите «Нет весов».\n\n"
        "<i>Бот был перезагружен. Если что-то не работает — пишите!</i>"
    )
    
    count = 0
    async for session in get_db():
        stmt = select(User).where(User.is_verified == True)
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
    asyncio.run(notify_testers())
