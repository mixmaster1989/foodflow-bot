#!/usr/bin/env python3
"""Script to notify all users about bot relaunch and reset their onboarding.

Usage:
    python scripts/notify_relaunch.py

This script:
1. Resets is_initialized=False for all users
2. Sends a push notification to all users with a button to re-onboard
"""
import asyncio
import logging

from aiogram import Bot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    import sys
    sys.path.insert(0, "/home/user1/foodflow-bot")

    from sqlalchemy import select, update

    from config import settings
    from database.base import get_db, init_db
    from database.models import User, UserSettings

    await init_db()

    bot = Bot(token=settings.BOT_TOKEN)

    async for session in get_db():
        # 1. Reset all users' is_initialized flag
        stmt = update(UserSettings).values(is_initialized=False)
        result = await session.execute(stmt)
        await session.commit()
        logger.info(f"Reset {result.rowcount} users' onboarding status")

        # 2. Get all users to notify
        users_stmt = select(User)
        users = (await session.execute(users_stmt)).scalars().all()

        success_count = 0
        fail_count = 0

        for user in users:
            try:
                await bot.send_message(
                    chat_id=user.id,
                    text=(
                        "🎉 <b>FoodFlow обновлен!</b>\n\n"
                        "Мы добавили новые функции:\n"
                        "• ⚖️ <b>Отслеживание веса</b> — записывай вес и следи за прогрессом\n"
                        "• 🔔 <b>Напоминания</b> — бот напомнит записать вес каждый день\n"
                        "• 🎂 <b>Учет возраста</b> — более точные расчеты КБЖУ\n\n"
                        "Пожалуйста, пройди настройку заново, чтобы активировать новые функции!"
                    ),
                    parse_mode="HTML",
                    reply_markup={
                        "inline_keyboard": [[
                            {"text": "🔄 Пройти настройку", "callback_data": "force_onboarding"}
                        ]]
                    }
                )
                success_count += 1
                logger.info(f"✅ Notified user {user.id}")
            except Exception as e:
                fail_count += 1
                logger.error(f"❌ Failed to notify {user.id}: {e}")

            # Rate limiting
            await asyncio.sleep(0.1)

        logger.info(f"\n📊 Results: {success_count} success, {fail_count} failed")

    await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
