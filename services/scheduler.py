"""Module for daily reminder scheduler.

Contains:
- start_scheduler: Initialize APScheduler for daily reminders
- send_weight_reminders: Job function to send daily weight prompts
"""
import logging
from datetime import datetime

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from database.base import get_db
from database.models import UserSettings

logger = logging.getLogger(__name__)

scheduler: AsyncIOScheduler | None = None


async def send_weight_reminders(bot: Bot) -> None:
    """Send daily weight reminder to all users with reminders enabled."""
    current_hour = datetime.now().strftime("%H")
    current_minute = datetime.now().strftime("%M")
    current_time = f"{current_hour}:{current_minute}"
    
    logger.info(f"Running weight reminder job at {current_time}")
    
    async for session in get_db():
        # Get all users with reminders enabled whose reminder_time matches current hour
        stmt = select(UserSettings).where(
            UserSettings.is_initialized == True,
            UserSettings.reminders_enabled == True,
        )
        settings_list = (await session.execute(stmt)).scalars().all()
        
        for settings in settings_list:
            # Check if reminder_time hour matches current hour
            reminder_hour = settings.reminder_time.split(":")[0] if settings.reminder_time else "09"
            if reminder_hour == current_hour:
                try:
                    await bot.send_message(
                        chat_id=settings.user_id,
                        text=(
                            "⚖️ <b>Доброе утро!</b>\n\n"
                            "Пора записать вес! Это поможет отслеживать прогресс.\n\n"
                            "Напиши свой вес (например: 72.5) или нажми кнопку ниже."
                        ),
                        parse_mode="HTML",
                        reply_markup={
                            "inline_keyboard": [[
                                {"text": "✏️ Записать вес", "callback_data": "weight_input"}
                            ]]
                        }
                    )
                    logger.info(f"Sent weight reminder to user {settings.user_id}")
                except Exception as e:
                    logger.error(f"Failed to send reminder to {settings.user_id}: {e}")


def start_scheduler(bot: Bot) -> AsyncIOScheduler:
    """Initialize and start the APScheduler for daily reminders."""
    global scheduler
    
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    
    # Run every hour at minute 0 to check which users need reminders
    scheduler.add_job(
        send_weight_reminders,
        CronTrigger(minute=0),  # Every hour at :00
        args=[bot],
        id="weight_reminders",
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("📅 Reminder scheduler started")
    
    return scheduler
