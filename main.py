import asyncio
import logging

from aiogram import Bot, Dispatcher

from config import settings
from database import migrations
from database.base import init_db
from handlers import (
    common,
    auth,
    onboarding,
    menu,
    i_ate,
    receipt,
    shopping,
    stats,
    fridge,
    recipes,
    user_settings,
    curator,
    saved_dishes,
    weight,
    base,
    universal_input,
    errors, 
    shopping_list,
    admin,
    support,
    correction,
    # global_input,
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

    # Register Middleware
    from handlers.auth import AuthMiddleware
    from middleware.admin_logger import AdminLoggerMiddleware
    
    dp.update.middleware(AdminLoggerMiddleware(bot)) # Logs and forwards to admin
    dp.update.middleware(AuthMiddleware())

    # Register Routers
    # IMPORTANT: shopping.router must be before receipt.router
    # to handle photos in scanning_labels state first
    dp.include_router(errors.router) # Catch errors globally
    dp.include_router(common.router)
    dp.include_router(admin.router) # Admin commands
    dp.include_router(support.router) # Contact Dev
    dp.include_router(onboarding.router)  # Onboarding must be after common
    dp.include_router(menu.router)  # Central menu router
    dp.include_router(i_ate.router)  # Quick food logging
    dp.include_router(curator.router)  # Curator dashboard
    dp.include_router(shopping.router)  # Must be before receipt.router!
    dp.include_router(receipt.router)
    dp.include_router(fridge.router)
    dp.include_router(recipes.router)
    dp.include_router(stats.router)
    dp.include_router(user_settings.router)
    dp.include_router(shopping_list.router)
    dp.include_router(weight.router)
    dp.include_router(correction.router)
    dp.include_router(saved_dishes.router)
    # dp.include_router(global_input.router) # DEPRECATED
    dp.include_router(universal_input.router) # Universal Handler (Text/Voice/Photo)

    # Start reminder scheduler
    from services.scheduler import start_scheduler
    start_scheduler(bot, dp)

    logging.info("🚀 FoodFlow Bot started!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
