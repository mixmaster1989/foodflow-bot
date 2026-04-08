
import asyncio
import logging
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from config import settings
from services.scheduler import send_admin_digest

logging.basicConfig(level=logging.INFO)

async def test_digest():
    bot = Bot(token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    print("🚀 Triggering Admin Daily Digest test...")
    try:
        await send_admin_digest(bot)
        print("✅ Digest sent successfully to admins!")
    except Exception as e:
        print(f"❌ Failed: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(test_digest())
