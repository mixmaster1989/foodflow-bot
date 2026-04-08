import asyncio
import json
import logging
import os
import sys
from aiogram import Bot, types
from aiogram.types import FSInputFile

# Добавляем путь к корню проекта
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- НАСТРОЙКИ КАМПАНИИ ---
DRY_RUN = False
GREETING_IMAGE = "assets/march_8_greetings.png"
REPORTS_FILE = "data/march_8_ai_gifts_final.json"

# Те, кому отправка не удалась (Зеленая группа)
FAILED_USERS = {
    5422141137: "Юлия Герасимова",
    295543071: "Ольга Антакова",
    5153798702: "Татьяна Безручкина",
    104202119: "Вера Писковацкова",
}

def split_text(text, limit=4000):
    chunks = []
    while len(text) > limit:
        split_pos = text.rfind('\n', 0, limit)
        if split_pos == -1:
            split_pos = limit
        chunks.append(text[:split_pos])
        text = text[split_pos:].lstrip()
    chunks.append(text)
    return chunks

async def send_campaign():
    bot = Bot(token=settings.BOT_TOKEN)
    with open(REPORTS_FILE, "r", encoding="utf-8") as f:
        reports = json.load(f)
    
    logger.info(f"--- ДОРАССЫЛКА ДЛЯ ЗЕЛЕНОЙ ГРУППЫ (DRY_RUN={DRY_RUN}) ---")
    
    count = 0
    for user_id, name in FAILED_USERS.items():
        report_text = reports.get(str(user_id))
        if not report_text: continue
        
        try:
            if DRY_RUN:
                logger.info(f"[DRY_RUN] Отправка чанками для {name} ({user_id})")
            else:
                # 1. Отправка картинки
                if os.path.exists(GREETING_IMAGE):
                    photo = FSInputFile(GREETING_IMAGE)
                    await bot.send_photo(chat_id=user_id, photo=photo)
                
                # 2. Отправка текста частями
                chunks = split_text(report_text)
                for i, chunk in enumerate(chunks):
                    await bot.send_message(chat_id=user_id, text=chunk, parse_mode="Markdown")
                    logger.info(f"✅ Чанк {i+1}/{len(chunks)} для {name} отправлен.")
                
                logger.info(f"🏁 Полный отчет для {name} доставлен.")
            
            count += 1
            await asyncio.sleep(1)
            await asyncio.sleep(0.5) # Пауза между пользователями
            
        except Exception as e:
            logger.error(f"❌ Ошибка для {name} ({user_id}): {e}")
            
    await bot.session.close()
    logger.info(f"--- РАССЫЛКА ЗАВЕРШЕНА. Всего адресатов: {count} ---")

if __name__ == "__main__":
    asyncio.run(send_campaign())
