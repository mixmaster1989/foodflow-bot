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

async def notify_summary():
    bot = Bot(token=settings.BOT_TOKEN)
    await init_db()
    
    msg_text = (
        "🌙 <b>Итоги дня: FoodFlow Bot v1.2</b>\n\n"
        "Мы завершили серию крупных обновлений. Спасибо за ваше активное тестирование!\n\n"
        "<b>Что сделано за сегодня:</b>\n"
        "1. 🛍️ <b>Убрана кнопка «Список покупок»</b> (по просьбам).\n"
        "2. 🧊 <b>Холодильник: Добавить еду</b>\n"
        "   - Теперь можно добавлять продукты вручную (через этикетку или фото блюда).\n"
        "3. 🍽️ <b>Я это съел</b>\n"
        "   - Бот спрашивает вес порции (или принимает «нет весов»).\n"
        "   - КБЖУ считается корректно.\n"
        "4. 📸 <b>Умное фото</b>\n"
        "   - Теперь можно кидать фото еды в любой момент.\n"
        "   - Добавлена кнопка «❄️ В холодильник» (чтобы не лазить по меню).\n"
        "5. 🔧 <b>Стабильность</b>\n"
        "   - Исправлены падения, конфликты процессов и ошибки кнопок.\n\n"
        "<b>План на завтра (по вашим заявкам):</b>\n"
        "- ✅ Возможность удалять позиции из чека перед добавлением.\n"
        "- ✅ Подтверждение перед сохранением в холодильник (чтобы не добавлялось «молча»).\n\n"
        "<i>Спокойной ночи и приятного аппетита!</i> 🍏"
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
    asyncio.run(notify_summary())
