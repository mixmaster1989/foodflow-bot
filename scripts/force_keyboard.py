import asyncio
import sys
from pathlib import Path

# Add root directory to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from aiogram import Bot
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from config import settings


async def send_keyboard(user_id):
    bot = Bot(token=settings.BOT_TOKEN)

    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏠 Главное меню")]
        ],
        resize_keyboard=True,
        persistent=True
    )

    try:
        await bot.send_message(
            chat_id=user_id,
            text="🛠 Тестовая отправка клавиатуры (Debug Script). Видно кнопку?",
            reply_markup=kb
        )
        print("Message sent successfully.")
    except Exception as e:
        print(f"Error sending message: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(send_keyboard(432823154))
