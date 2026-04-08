import asyncio
import logging
import sys
import os
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import settings

logging.basicConfig(level=logging.INFO)

async def rescue_user():
    bot = Bot(token=settings.BOT_TOKEN)
    target_id = 321100568
    
    # 1. Send the NPC timeout message
    npc_text = (
        "🤖 <i>Бип-боп...</i>\n\n"
        "Время ожидания фотографий истекло! 🕒\n"
        "Вы слишком долго смотрели вглубь холодильника. Ваш виртуальный профиль сохранен.\n\n"
        "Возвращаю вас в Главное меню!"
    )
    
    # Minimal Keyboard mimicking main menu
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🍽️ Я СЪЕЛ!", callback_data="menu_ate")],
        [InlineKeyboardButton(text="🛒 Я купил", callback_data="menu_bought")],
        [InlineKeyboardButton(text="📊 Дневник", callback_data="history_today"), 
         InlineKeyboardButton(text="💧 Вода", callback_data="menu_water")],
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings_main"),
         InlineKeyboardButton(text="💎 PRO Подписка", callback_data="buy_subscription")]
    ])
    
    try:
        await bot.send_message(
            chat_id=target_id, 
            text=npc_text, 
            parse_mode="HTML",
            reply_markup=keyboard
        )
        logging.info("Rescue complete! User 321100568 received the NPC message and menu.")
    except Exception as e:
        logging.error(f"Failed to send manual menu: {e}")
        
    await bot.session.close()

if __name__ == "__main__":
    asyncio.run(rescue_user())
