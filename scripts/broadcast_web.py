import asyncio
import logging
import sys
import os
from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import settings
from api.auth import create_access_token
from database.models import User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("broadcast")

async def broadcast_web():
    bot = Bot(token=settings.BOT_TOKEN)
    
    # Database setup
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    
    async with async_session() as session:
        stmt = select(User)
        result = await session.execute(stmt)
        users = result.scalars().all()
        
    logger.info(f"Found {len(users)} users. Starting broadcast...")
    
    success_count = 0
    fail_count = 0
    
    for user in users:
        user_id = user.id
        token = create_access_token(data={"sub": user_id})
        link = f"https://tretyakov-igor.tech/?token={token}"
        
        # Message 1: Magic Link
        msg1_text = (
            "🌐 <b>Ваша персональная ссылка для входа:</b>\n\n"
            f"<code>{link}</code>\n\n"
            "☝️ Нажмите на ссылку выше, чтобы скопировать.\n\n"
            "Откройте её в любом браузере (Chrome, Safari) — вы войдёте в свой аккаунт <b>без Telegram</b>.\n\n"
            "💡 <i>Ссылка действует 30 дней. Сохраните в закладки!</i>"
        )
        
        # Message 2: Explanation
        msg2_text = (
            "❤️ <b>Важное обновление от команды FoodFlow</b>\n\n"
            "Мы знаем, что Telegram в последнее время работает нестабильно — лаги, задержки, сбои даже через VPN. Это не зависит от нас, но <b>мы не хотим, чтобы вы теряли доступ к своему дневнику питания и прогрессу</b>.\n\n"
            "Поэтому мы сделали для вас <b>полноценную веб-версию</b> FoodFlow! 🚀\n\n"
            "<b>Что нужно сделать (30 секунд):</b>\n"
            "1️⃣ Откройте ссылку выше в браузере (Chrome, Safari, любом).\n"
            "2️⃣ Сохраните страницу в закладки или на рабочий стол телефона.\n"
            "3️⃣ Готово! Теперь ваш дневник питания, история, графики веса — всё доступно <b>даже если Telegram полностью ляжет</b>.\n\n"
            "Ваши данные никуда не денутся. Мы на вашей стороне. 💪\n\n"
            "С заботой, команда FoodFlow 🥗"
        )
        
        try:
            # Send Message 1
            await bot.send_message(chat_id=user_id, text=msg1_text, parse_mode="HTML")
            await asyncio.sleep(0.3) # Short delay
            
            # Send Message 2
            await bot.send_message(chat_id=user_id, text=msg2_text, parse_mode="HTML")
            await asyncio.sleep(0.7) # Delay between users
            
            success_count += 1
            logger.info(f"Sent to {user_id} ({success_count}/{len(users)})")
            
        except Exception as e:
            fail_count += 1
            logger.warning(f"Failed to send to {user_id}: {e}")
            
    logger.info(f"Broadcast complete! Success: {success_count}, Failed: {fail_count}")
    await bot.session.close()

if __name__ == "__main__":
    asyncio.run(broadcast_web())
