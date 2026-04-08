import asyncio
import logging
from datetime import datetime, timedelta
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.base import async_session
from sqlalchemy import select, and_
from database.models import UserSettings, ConsumptionLog
from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=settings.BOT_TOKEN)

async def main():
    target_users = []
    
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        # Test mode for specific user
        target_users.append(int(sys.argv[1]))
        logger.info(f"TEST MODE: Broadcasting only to user {sys.argv[1]}")
    else:
        # User requested specific active candidates
        target_users = [5153798702, 1734637013, 1015270932, 295543071]
        logger.info(f"LIVE MODE: Broadcasting to predefined VIP active users: {target_users}")
        
        if not target_users:
            return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, буду вести каждый день", callback_data="guide_test:accept")],
        [InlineKeyboardButton(text="❌ Нет, сейчас нет времени на это", callback_data="guide_test:decline")]
    ])
    
    text = (
        "👋 Привет! Это создатели бота FoodFlow.\n\n"
        "Мы собрали новую, мощную функцию: <b>Проактивный ИИ-Гид</b>. Он не просто считает калории, а анализирует твои цели, "
        "видит твой холодильник, помнит, чем ты пользовался, и дает умные советы <i>персонально тебе</i>.\n\n"
        "<b>Нам нужны активные тестеры!</b>\n"
        "Мы готовы выдать тебе PRO-статус бесплатно на 30 дней. Условие только одно: <b>ты должен регулярно вести дневник питания в боте</b>, чтобы система работала и обучалась. Идеально — каждый день.\n\n"
        "Хочешь попробовать ИИ-Гида бесплатно и прокачать свою форму?"
    )

    success_count = 0
    for uid in target_users:
        try:
            await bot.send_message(uid, text, reply_markup=keyboard, parse_mode="HTML")
            success_count += 1
            logger.info(f"Sent poll to {uid}")
            await asyncio.sleep(0.3)
        except Exception as e:
            logger.error(f"Failed to send to {uid}: {e}")
            
    logger.info(f"Broadcast complete! Successfully sent to {success_count} users.")
    await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
