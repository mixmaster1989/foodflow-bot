import asyncio
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiogram import Bot
from config import settings

async def main():
    bot = Bot(token=settings.BOT_TOKEN)
    user_id = 295543071  # Olga
    
    text = (
        "Ольга, всё починили! ✅\n\n"
        "1. Зайдите в <b>Главное меню</b>.\n"
        "2. Нажмите <b>Настройки</b> (шестеренка).\n"
        "3. Там появилась кнопка <b>✏️ Изменить профиль</b>.\n\n"
        "Нажмите её, и я заново спрошу пол, возраст и правильный рост."
    )
    
    try:
        await bot.send_message(chat_id=user_id, text=text, parse_mode="HTML")
        print(f"Notification sent to {user_id}")
    except Exception as e:
        print(f"Failed to send notification: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
