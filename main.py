import asyncio
import logging

from aiogram import Bot, Dispatcher

from config import settings
from database import migrations
from database.base import init_db
from handlers import (
    common,
    fridge,
    menu,
    receipt,
    recipes,
    shopping,
    shopping_list,
    stats,
    user_settings,
)


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        handlers=[
            logging.FileHandler("foodflow.log", encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

    # Initialize DB
    await init_db()
    await migrations.run_migrations()

    bot = Bot(token=settings.BOT_TOKEN)
    dp = Dispatcher()

    # Register Routers
    dp.include_router(common.router)
    dp.include_router(menu.router)  # Central menu router
    dp.include_router(receipt.router)
    dp.include_router(fridge.router)
    dp.include_router(recipes.router)
    dp.include_router(stats.router)
    dp.include_router(shopping.router)
    dp.include_router(user_settings.router)
    dp.include_router(shopping_list.router)

    logging.info("🚀 FoodFlow Bot started!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
