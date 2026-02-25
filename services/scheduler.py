"""Module for daily reminder scheduler.

Contains:
- start_scheduler: Initialize APScheduler for daily reminders
- send_weight_reminders: Job function to send daily weight prompts
- send_daily_summaries: Job function to send daily nutrition reports/nudges
"""
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from daily_nutrition_report import run_daily_report
from database.base import get_db
from database.models import UserSettings
from handlers.weight import WeightStates
from services.reports import generate_daily_report

logger = logging.getLogger(__name__)

scheduler: AsyncIOScheduler | None = None


async def send_weight_reminders(bot: Bot, dp: Dispatcher) -> None:
    """Send daily weight reminder to all users with reminders enabled."""
    current_hour = datetime.now().strftime("%H")
    current_minute = datetime.now().strftime("%M")
    current_time = f"{current_hour}:{current_minute}"

    logger.info(f"Running weight reminder job at {current_time}")

    async for session in get_db():
        # Get ALL users with reminders enabled (removed is_initialized filter)
        stmt = select(UserSettings).where(
            UserSettings.reminders_enabled,
        )
        settings_list = (await session.execute(stmt)).scalars().all()

        for settings in settings_list:
            # Check if reminder_time hour matches current hour
            reminder_hour = settings.reminder_time.split(":")[0] if settings.reminder_time else "09"
            if reminder_hour == current_hour:
                try:
                    # Set user state to waiting_for_morning_weight
                    state = FSMContext(
                        storage=dp.storage,
                        key=StorageKey(
                            bot_id=bot.id,
                            chat_id=settings.user_id,
                            user_id=settings.user_id
                        )
                    )
                    await state.set_state(WeightStates.waiting_for_morning_weight)

                    prompt_suffix = "(например: 72.5)"
                    if settings.weight:
                        prompt_suffix = f"(прошлый: {settings.weight})"

                    await bot.send_message(
                        chat_id=settings.user_id,
                        text=(
                            "⚖️ <b>Доброе утро!</b>\n\n"
                            "Пора записать вес! Это поможет отслеживать прогресс.\n\n"
                            f"Напиши свой вес {prompt_suffix} или нажми кнопку ниже."
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


async def send_daily_summaries(bot: Bot) -> None:
    """Send daily nutrition summaries to ALL users whose summary_time matches current hour."""
    from datetime import datetime
    current_hour = datetime.now().strftime("%H:00")
    logger.info(f"Running daily summary check for hour {current_hour}")

    async for session in get_db():
        # Get ALL users whose summary_time matches current hour (removed is_initialized filter)
        stmt = select(UserSettings).where(
            UserSettings.summary_time == current_hour
        )
        settings_list = (await session.execute(stmt)).scalars().all()

        logger.info(f"Found {len(settings_list)} users for summary at {current_hour}")

        for settings in settings_list:
            try:
                report_text = await generate_daily_report(settings.user_id)
                if report_text:
                    await bot.send_message(
                        chat_id=settings.user_id,
                        text=report_text,
                        parse_mode="HTML"
                    )
                    logger.info(f"Sent daily summary to {settings.user_id}")
            except Exception as e:
                logger.error(f"Failed to send summary to {settings.user_id}: {e}")


def start_scheduler(bot: Bot, dp: Dispatcher) -> AsyncIOScheduler:
    """Initialize and start the APScheduler."""
    global scheduler

    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")

    # 1. Weight Reminders (Hourly check)
    scheduler.add_job(
        send_weight_reminders,
        CronTrigger(minute=0),
        args=[bot, dp],
        id="weight_reminders",
        replace_existing=True
    )

    # 2. Daily Summaries (Hourly check - sends based on user's summary_time)
    scheduler.add_job(
        send_daily_summaries,
        CronTrigger(minute=0),  # Every hour at :00
        args=[bot],
        id="daily_summaries",
        replace_existing=True
    )

    # TODO [CURATOR-3.1]: Add curator morning summary job
    # scheduler.add_job(
    #     send_curator_summaries,  # from services.curator_analytics
    #     CronTrigger(hour=8, minute=0),  # Every day at 8:00 AM
    #     args=[bot],
    #     id="curator_summaries",
    #     replace_existing=True
    # )

    # 3. Visual Nutrition Report (12:00 MSK)
    scheduler.add_job(
        run_daily_report,
        CronTrigger(hour=12, minute=0),
        id="visual_daily_report",
        replace_existing=True
    )

    scheduler.start()
    logger.info("📅 Reminder scheduler started")

    return scheduler
