import asyncio
import logging
from aiogram import Bot, Dispatcher
from config import TELEGRAM_TOKEN
from database.base import init_db
from handlers import start, dream, payment, admin

logging.basicConfig(level=logging.INFO)

async def main():
    await init_db()
    
    bot = Bot(token=TELEGRAM_TOKEN)
    dp = Dispatcher()

    dp.include_routers(
        start.router,
        payment.router,
        admin.router,
        dream.router
    )

    print("🔮 Бот-Оракул запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
