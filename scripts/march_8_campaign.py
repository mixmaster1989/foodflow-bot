import asyncio
import logging
import os
import sys

# Добавляем путь к корню проекта
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiogram import Bot
from aiogram.types import FSInputFile
from config import settings

# --- КОНФИГУРАЦИЯ ---
DRY_RUN = False  # Отключаем безопасный режим для реальной отправки

# Группа: Мало или нет данных
FEMALE_USERS_LOW_DATA = {
    7899005241: "Даха Ткачева",
    5204589721: "Наталия Денисова",
    5263406733: "Альфия Ольга",
    7846721167: "Елена Одринская",
    7206006611: "Nensiup$$",
    495294354: "Икар IT - отдел",
}

CONGRATS_PHOTO_PATH = "assets/march_8_greetings.png"

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def send_congrats(bot: Bot, user_id: int, name: str, text: str, photo_path: str = None):
    """Отправка поздравления одному пользователю."""
    try:
        if DRY_RUN:
            logger.info(f"[DRY_RUN] Отправка {user_id} ({name}). Текст: {text[:50]}... Файл: {photo_path}")
            return True
        
        # 1. Отправка фото (если есть)
        if photo_path and os.path.exists(photo_path):
            photo = FSInputFile(photo_path)
            await bot.send_photo(chat_id=user_id, photo=photo, caption=text, parse_mode="HTML")
        else:
            # 2. Только текст
            await bot.send_message(chat_id=user_id, text=text, parse_mode="HTML")
            
        logger.info(f"✅ Успешно отправлено пользователю {user_id} ({name})")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке {user_id} ({name}): {e}")
        return False

async def main():
    logger.info(f"🚀 Запуск кампании к 8 марта (Группа: МАЛО ДАННЫХ). Режим DRY_RUN: {DRY_RUN}")
    
    bot = Bot(token=settings.BOT_TOKEN)
    
    for user_id, name in FEMALE_USERS_LOW_DATA.items():
        message_text = (
            f"🌸 <b>С 8 марта, {name}!</b> 🌸\n\n"
            "Команда <b>FoodFlow</b> поздравляет вас с праздником весны! Желаем энергии, прекрасного настроения и достижения всех ваших целей.\n\n"
            "Пусть эта весна станет временем новых полезных привычек! Начните вести дневник питания в боте уже сегодня — это первый шаг к телу вашей мечты. Мы всегда рядом, чтобы помочь! 🚀"
        )
        
        await send_congrats(bot, user_id, name, message_text, CONGRATS_PHOTO_PATH)
        
        if not DRY_RUN:
            await asyncio.sleep(0.5)

    await bot.session.close()
    logger.info("🏁 Кампания завершена.")

if __name__ == "__main__":
    asyncio.run(main())
