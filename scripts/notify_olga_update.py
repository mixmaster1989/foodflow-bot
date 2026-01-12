import asyncio
import logging
import sys
import os

# Add parent directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiogram import Bot
from config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TARGET_USER_ID = 295543071 # Olga

MESSAGE_TEXT = (
    "✨ <b>Большое обновление!</b> ✨\n\n"
    "Я научился трем важным вещам:\n\n"
    "1️⃣ <b>Умная очередь фото</b> 📸\n"
    "Можно отправлять сколько угодно фотографий сразу (хоть 10 штук!). "
    "Я выстрою их в очередь и аккуратно обработаю по одной, чтобы ничего не потерять.\n\n"
    "2️⃣ <b>Едим по чуть-чуть</b> 🍽️\n"
    "Теперь не обязательно удалять продукт целиком. Нажмите «Съесть», и появится выбор:\n"
    "• ⚖️ В граммах (например, 50г)\n"
    "• 🧩 В штуках (например, 0.5 шт)\n"
    "• 🍽️ Целиком (1 шт)\n\n"
    "3️⃣ <b>Удобное меню</b> 📱\n"
    "Кнопка <b>«🧊 Холодильник»</b> теперь большая и находится в самом верху меню, "
    "чтобы доступ к продуктам был мгновенным.\n\n"
    "Приятного пользования! 🍏"
)

async def main():
    print(f"Sending notification to {TARGET_USER_ID}...")
    bot = Bot(token=settings.BOT_TOKEN)
    try:
        await bot.send_message(chat_id=TARGET_USER_ID, text=MESSAGE_TEXT, parse_mode="HTML")
        print("Message sent successfully!")
    except Exception as e:
        print(f"Failed to send message: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
