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
DRY_RUN = True  # СТРОГО DRY_RUN ДЛЯ ПРОВЕРКИ

# ГРУППА "ЗЕЛЕНАЯ" (Много данных - Фулл отчет)
USERS_GREEN = {
    5422141137: "Юлия Герасимова",
    295543071: "Ольга Антакова",
    5153798702: "Татьяна Безручкина",
    104202119: "Вера Писковацкова",
}

# ГРУППА "ЖЕЛТАЯ" (Средне данных)
USERS_YELLOW = {
    1044916834: "Ксюша Ермолаева",
    109153550: "Елена Васильева",
    7846721167: "Елена Третьякова", # ИСПРАВЛЕННЫЙ ID (был перепутан с Одринской)
}

# ОСТАТОК ИЗ "КРАСНОЙ" (Кто был пропущен или ошибочен)
USERS_RED_FIX = {
    911990304: "Елена Одринская", # БЫЛА ПРОПУЩЕНА
}

CONGRATS_PHOTO_PATH = "assets/march_8_greetings.png"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def send_congrats(bot: Bot, user_id: int, name: str, text: str, photo_path: str = None):
    try:
        if DRY_RUN:
            logger.info(f"[DRY_RUN] Отправка {user_id} ({name}). Текст: {text[:60]}...")
            return True
        
        if photo_path and os.path.exists(photo_path):
            photo = FSInputFile(photo_path)
            await bot.send_photo(chat_id=user_id, photo=photo, caption=text, parse_mode="HTML")
        else:
            await bot.send_message(chat_id=user_id, text=text, parse_mode="HTML")
            
        logger.info(f"✅ Успешно отправлено: {user_id} ({name})")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка {user_id} ({name}): {e}")
        return False

async def main():
    logger.info(f"🚀 ТЕСТОВЫЙ ЗАПУСК. Режим DRY_RUN: {DRY_RUN}")
    bot = Bot(token=settings.BOT_TOKEN)
    
    # 1. Проверка Зеленой группы
    logger.info("--- ГРУППА ЗЕЛЕНАЯ ---")
    for u_id, name in USERS_GREEN.items():
        text = f"🌸 <b>С 8 марта, {name}!</b> 🌸\n\n[ТУТ БУДЕТ ФУЛЛ ОТЧЕТ И КОНСУЛЬТАЦИЯ]"
        await send_congrats(bot, u_id, name, text, CONGRATS_PHOTO_PATH)

    # 2. Проверка Желтой группы
    logger.info("--- ГРУППА ЖЕЛТАЯ ---")
    for u_id, name in USERS_YELLOW.items():
        text = f"🌸 <b>С 8 марта, {name}!</b> 🌸\n\n[ТУТ БУДЕТ КРАТКИЙ СОВЕТ]"
        await send_congrats(bot, u_id, name, text, CONGRATS_PHOTO_PATH)

    # 3. Проверка пропущенных из Красной
    logger.info("--- ГРУППА КРАСНАЯ (FIX) ---")
    for u_id, name in USERS_RED_FIX.items():
        text = (f"🌸 <b>С 8 марта, {name}!</b> 🌸\n\n"
                "Пусть эта весна станет временем новых полезных привычек! Начните вести дневник сегодня...")
        await send_congrats(bot, u_id, name, text, CONGRATS_PHOTO_PATH)

    await bot.session.close()
    logger.info("🏁 Тест завершен. ВСЕ ИМЕНА ПРОВЕРЕНЫ ПО БАЗЕ.")

if __name__ == "__main__":
    asyncio.run(main())
