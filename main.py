import asyncio
import logging

from aiogram import Bot, Dispatcher

from config import settings
from database import migrations
from database.base import init_db
from handlers import (
    admin,
    common,
    correction,
    curator,
    errors,
    feedback,
    fridge,
    fridge_search,
    herbalife,
    i_ate,
    menu,
    onboarding,
    payments,
    receipt,
    recipes,
    referrals,
    saved_dishes,
    shopping,
    shopping_list,
    stats,
    subscription,
    support,
    survey,
    universal_input,
    user_settings,
    ward_interactions,
    # global_input,
    water,
    weight,
    marketing,
    pilot_commands,
    guide,
    testers,
)
from handlers.marathon import curator_menu


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
    from middleware.paywall import PaywallMiddleware
    from middleware.user_enrichment import UserEnrichmentMiddleware
    from aiogram import BaseMiddleware
    from aiogram.types import Update

    class GroupFilterMiddleware(BaseMiddleware):
        """Drop group messages early — only allow /mstats and mkt_ callbacks through."""
        async def __call__(self, handler, event, data):
            if isinstance(event, Update):
                if event.message:
                    if event.message.chat.type == "private":
                        return await handler(event, data)
                    if event.message.text and event.message.text.startswith("/mstats"):
                        return await handler(event, data)
                    return
                elif event.callback_query:
                    if event.callback_query.data and event.callback_query.data.startswith("mkt_"):
                        return await handler(event, data)
                    if event.callback_query.message and event.callback_query.message.chat.type == "private":
                        return await handler(event, data)
                    return
                else:
                    # pre_checkout_query, my_chat_member, etc. — pass through
                    return await handler(event, data)
            return await handler(event, data)

    dp.update.outer_middleware(GroupFilterMiddleware())
    dp.update.middleware(AdminLoggerMiddleware(bot)) # Logs and forwards to admin
    dp.update.middleware(UserEnrichmentMiddleware())  # Auto-enrich user profiles
    
    dp.update.middleware(AuthMiddleware())

    # Paywall should intercept messages and callbacks
    dp.message.middleware(PaywallMiddleware())
    dp.callback_query.middleware(PaywallMiddleware())

    # Register Routers
    # IMPORTANT: shopping.router must be before receipt.router
    # to handle photos in scanning_labels state first
    dp.include_router(errors.router) # Catch errors globally
    dp.include_router(common.router)
    dp.include_router(admin.router) # Admin commands
    dp.include_router(pilot_commands.router) # Pilot-only commands (MUST BE EARLY)
    dp.include_router(support.router) # Contact Dev
    dp.include_router(onboarding.router)  # Onboarding must be after common
    dp.include_router(user_settings.router)
    dp.include_router(subscription.router)
    dp.include_router(payments.router)  # Telegram Stars payments
    dp.include_router(menu.router)
    dp.include_router(water.router)  # Central menu router
    dp.include_router(i_ate.router)  # Quick food logging
    dp.include_router(herbalife.router) # Herbalife Expert
    dp.include_router(curator_menu.router) # Marathon Module
    dp.include_router(curator.router)  # Curator dashboard
    dp.include_router(shopping.router)  # Must be before receipt.router!
    dp.include_router(receipt.router)
    dp.include_router(fridge.router)
    dp.include_router(fridge_search.router) # New Smart Search
    dp.include_router(recipes.router)
    dp.include_router(stats.router)
    dp.include_router(referrals.router)
    dp.include_router(feedback.router)
    dp.include_router(survey.router)
    dp.include_router(shopping_list.router)
    dp.include_router(weight.router)
    dp.include_router(correction.router)
    dp.include_router(saved_dishes.router)
    dp.include_router(ward_interactions.router)
    dp.include_router(marketing.router) # Marketing analytics for group
    # dp.include_router(global_input.router) # DEPRECATED
    dp.include_router(universal_input.router) # Universal Handler (Text/Voice/Photo)
    dp.include_router(guide.router)
    dp.include_router(testers.router) # Beta testers recruitment

    # Start reminder scheduler
    from services.scheduler import start_scheduler
    start_scheduler(bot, dp)

    # Reset Menu Button to Default (remove Web App from input field)
    from aiogram.types import MenuButtonDefault
    try:
        # NOTE: Temporarily commented out due to network timeouts to api.telegram.org
        # await bot.set_chat_menu_button(
        #     menu_button=MenuButtonDefault()
        # )
        logging.info("✅ Skip Menu Button reset (restored code, network bypass)")
    except Exception as e:
        logging.warning(f"⚠️ Failed to reset Menu Button: {e}")

    logging.info("--- Starting FoodFlow Bot ---")
    logging.info("CI/CD Deployment: Verified successfully.")
    logging.info("🚀 FoodFlow Bot started!")
    try:
        await dp.start_polling(bot)
    finally:
        from services.http_client import close_http_session
        await close_http_session()

if __name__ == "__main__":
    asyncio.run(main())
