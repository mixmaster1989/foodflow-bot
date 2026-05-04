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
from sqlalchemy import and_, select, func

from services.daily_nutrition_report import run_daily_report
from database.base import get_db
from database.models import Subscription, User, UserSettings, ConsumptionLog, PAYMENT_SOURCE_TRIAL
from handlers.weight import WeightStates
from services.reports import (
    generate_curator_morning_summary,
    generate_daily_report,
    generate_ward_ai_report,
    generate_admin_daily_digest,
)

logger = logging.getLogger(__name__)

scheduler: AsyncIOScheduler | None = None


async def safe_send_message(bot: Bot, chat_id: int, **kwargs) -> bool:
    """Send message with automatic handling of blocked/deleted users.

    Returns True if sent successfully, False if user is unreachable.
    Sets User.is_blocked=True so future mailings skip this user.
    """
    try:
        await bot.send_message(chat_id=chat_id, **kwargs)
        return True
    except Exception as e:
        error_text = str(e).lower()
        if "bot was blocked" in error_text or "chat not found" in error_text or "user is deactivated" in error_text:
            logger.warning(f"User {chat_id} is unreachable, marking as blocked: {e}")
            try:
                async for session in get_db():
                    user = await session.get(User, chat_id)
                    if user and not user.is_blocked:
                        user.is_blocked = True
                        await session.commit()
                        logger.info(f"User {chat_id} marked as blocked in DB")
                    break
            except Exception:
                pass
            return False
        else:
            logger.error(f"Failed to send to {chat_id}: {e}")
            return False


async def send_weight_reminders(bot: Bot, dp: Dispatcher) -> None:
    """Send daily weight reminder to all users with reminders enabled."""
    current_hour = datetime.now().strftime("%H")
    current_minute = datetime.now().strftime("%M")
    current_time = f"{current_hour}:{current_minute}"

    logger.info(f"Running weight reminder job at {current_time}")

    async for session in get_db():
        stmt = (
            select(UserSettings)
            .join(User, UserSettings.user_id == User.id)
            .where(
                and_(
                    UserSettings.reminders_enabled,
                    UserSettings.is_initialized == True,
                    User.is_blocked.is_not(True),
                )
            )
        )
        settings_list = (await session.execute(stmt)).scalars().all()

        for settings in settings_list:
            reminder_hour = settings.reminder_time.split(":")[0] if settings.reminder_time else "09"
            if reminder_hour == current_hour:
                try:
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

                    sent = await safe_send_message(
                        bot,
                        settings.user_id,
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
                    if sent:
                        logger.info(f"Sent weight reminder to user {settings.user_id}")
                except Exception as e:
                    logger.error(f"Failed to send reminder to {settings.user_id}: {e}")


async def send_daily_summaries(bot: Bot) -> None:
    """Send daily nutrition summaries to ALL users whose summary_time matches current hour."""
    from datetime import datetime
    current_hour = datetime.now().strftime("%H:00")
    logger.info(f"Running daily summary check for hour {current_hour}")

    async for session in get_db():
        # Get ALL users whose summary_time matches current hour AND who are initialized
        stmt = select(UserSettings).where(
            and_(
                UserSettings.summary_time == current_hour,
                UserSettings.is_initialized == True
            )
        )
        settings_list = (await session.execute(stmt)).scalars().all()

        logger.info(f"Found {len(settings_list)} users for summary at {current_hour}")

        for settings in settings_list:
            try:
                report_text = await generate_daily_report(settings.user_id)
                if report_text:
                    sent = await safe_send_message(
                        bot, settings.user_id,
                        text=report_text,
                        parse_mode="HTML"
                    )
                    if sent:
                        logger.info(f"Sent daily summary to {settings.user_id}")
            except Exception as e:
                logger.error(f"Failed to send summary to {settings.user_id}: {e}")


async def send_curator_summaries(bot: Bot) -> None:
    """Send morning summaries to curators whose curator_summary_time matches current hour.

    Sends TWO messages per curator:
    1. Text summary with detailed food logs per ward (what + when).
    2. AI nutritionist photo card for each active ward.
    """
    import asyncio

    from aiogram.types import BufferedInputFile

    from services.image_renderer import draw_daily_card

    current_hour = datetime.now().strftime("%H:00")
    logger.info(f"Running curator summary check for hour {current_hour}")

    async for session in get_db():
        # Find all curators (users who have wards)
        from sqlalchemy import distinct
        curator_ids_stmt = select(distinct(User.curator_id)).where(
            User.curator_id.isnot(None)
        )
        curator_ids = (await session.execute(curator_ids_stmt)).scalars().all()

        logger.info(f"Found {len(curator_ids)} curators to check")

        for curator_id in curator_ids:
            # Check if curator's summary time matches current hour
            curator_settings_stmt = select(UserSettings).where(
                UserSettings.user_id == curator_id
            )
            curator_settings = (await session.execute(curator_settings_stmt)).scalar_one_or_none()

            curator_time = "08:00"
            if curator_settings and curator_settings.curator_summary_time:
                curator_time = curator_settings.curator_summary_time

            if curator_time != current_hour:
                continue

            logger.info(f"Sending curator summary to {curator_id}")

            try:
                # MESSAGE 1: Text summary with detailed logs
                summary_text = await generate_curator_morning_summary(curator_id)
                if summary_text:
                    sent = await safe_send_message(
                        bot, curator_id,
                        text=summary_text,
                        parse_mode="HTML"
                    )
                    if sent:
                        logger.info(f"Sent text summary to curator {curator_id}")

                # MESSAGE 2: AI photo cards per active ward
                wards_stmt = select(User).where(User.curator_id == curator_id)
                wards = (await session.execute(wards_stmt)).scalars().all()

                for ward in wards:
                    try:
                        report_data = await generate_ward_ai_report(ward.id)
                        if not report_data:
                            continue

                        # Generate image card
                        image_bio = draw_daily_card(
                            user_name=report_data["ward_name"],
                            target_date=report_data["date"],
                            logs=report_data["logs"],
                            total_metrics=report_data["totals"],
                            goals=report_data["goals"]
                        )

                        photo = BufferedInputFile(image_bio.getvalue(), filename="ward_report.png")
                        caption = (
                            f"🧠 <b>AI-нутрициолог: {report_data['ward_name']}</b>\n"
                            f"📅 {report_data['date'].strftime('%d.%m.%Y')}\n\n"
                            f"{report_data['ai_text']}"
                        )

                        # Telegram caption limit is 1024 chars
                        if len(caption) > 1024:
                            # Send photo with short caption, then text separately
                            short_caption = (
                                f"🧠 <b>AI-нутрициолог: {report_data['ward_name']}</b>\n"
                                f"📅 {report_data['date'].strftime('%d.%m.%Y')}"
                            )
                            await bot.send_photo(
                                chat_id=curator_id,
                                photo=photo,
                                caption=short_caption,
                                parse_mode="HTML"
                            )
                            await bot.send_message(
                                chat_id=curator_id,
                                text=report_data['ai_text'],
                                parse_mode="HTML"
                            )
                        else:
                            await bot.send_photo(
                                chat_id=curator_id,
                                photo=photo,
                                caption=caption,
                                parse_mode="HTML"
                            )

                        logger.info(f"Sent AI report for ward {ward.id} to curator {curator_id}")
                        await asyncio.sleep(1.0)  # Rate limit

                    except Exception as e:
                        logger.error(f"Failed AI report for ward {ward.id}: {e}", exc_info=True)

            except Exception as e:
                logger.error(f"Failed curator summary for {curator_id}: {e}", exc_info=True)
        break


async def expire_subscriptions(bot: Bot) -> None:
    """Check for expired one-time subscriptions and downgrade to free.

    Runs every hour. Only affects subscriptions where auto_renew=False
    (one-time purchases). Auto-renewing subscriptions are managed by Telegram.
    """
    now = datetime.now()
    logger.info(f"Checking for expired subscriptions at {now.strftime('%H:%M')}")

    async for session in get_db():
        # Find expired one-time subscriptions
        stmt = select(Subscription).where(
            and_(
                Subscription.is_active == True,  # noqa: E712
                Subscription.auto_renew == False,  # noqa: E712
                Subscription.tier != "free",
                Subscription.expires_at != None,  # noqa: E711
                Subscription.expires_at <= now,
            )
        )
        result = await session.execute(stmt)
        expired_subs = result.scalars().all()

        for sub in expired_subs:
            old_tier = sub.tier
            sub.tier = "free"
            sub.is_active = True  # Keep active but as free
            logger.info(f"Subscription expired: user={sub.user_id}, {old_tier} -> free")

            try:
                await safe_send_message(
                    bot, sub.user_id,
                    text=(
                        f"⏰ <b>Подписка истекла</b>\n\n"
                        f"Ваша подписка <b>{old_tier.upper()}</b> завершилась.\n"
                        f"Вы переведены на бесплатный тариф.\n\n"
                        f"Чтобы продлить, откройте /start → 💎 Подписки"
                    ),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error(f"Failed to notify user {sub.user_id} about expiration: {e}")

        if expired_subs:
            await session.commit()
            logger.info(f"Expired {len(expired_subs)} subscription(s)")
        break


async def send_onboarding_reminders(bot: Bot) -> None:
    """Send reminder to users who started but didn't finish onboarding after 2h."""
    from datetime import datetime, timedelta
    now = datetime.now()
    threshold = now - timedelta(hours=2)
    logger.info("Running onboarding reminder check...")

    async for session in get_db():
        stmt = select(User).where(
            and_(
                User.created_at <= threshold,
                User.onboarding_reminded == False,
                User.is_blocked.is_not(True),
            )
        )
        users = (await session.execute(stmt)).scalars().all()

        reminded_count = 0
        for user in users:
            # Skip mock/test users that trigger Bad Request: chat not found
            if user.id in [999999999, 123456789, 987654321]:
                continue
                
            # Check if they have UserSettings (meaning they finished onboarding)
            settings_stmt = select(UserSettings).where(UserSettings.user_id == user.id)
            settings = (await session.execute(settings_stmt)).scalar_one_or_none()

            if not settings:
                try:
                    sent = await safe_send_message(
                        bot, user.id,
                        text=(
                            "⏳ <b>Эй, мы тебя потеряли!</b>\n\n"
                            "Мы обратили внимание, что ты запустил FoodFlow, но так и не завершил настройку профиля. А ведь там тебя ждет подарок — <b>7 дней полного PRO-доступа</b> к AI-распознаванию еды и чекам! 🎁\n\n"
                            "Настройка займет ровно 30 секунд. Просто нажми на команду /start и ответь на пару вопросов (рост, вес, цель), чтобы умный алгоритм смог рассчитать твою норму.\n\n"
                            "Попробуешь? Жми 👉 /start"
                        ),
                        parse_mode="HTML"
                    )
                    user.onboarding_reminded = True
                    if sent:
                        reminded_count += 1
                        logger.info(f"Sent onboarding reminder to {user.id}")
                except Exception as e:
                    logger.error(f"Failed to send onboarding reminder to {user.id}: {e}")
            else:
                user.onboarding_reminded = True

        if users:
            await session.commit()
            
        logger.info(f"Sent {reminded_count} onboarding reminders.")
        break


async def send_admin_digest(bot: Bot) -> None:
    """Send global daily digest to all admins."""
    logger.info("Running admin daily digest job")
    
    try:
        digest_text = await generate_admin_daily_digest()
        from config import settings
        
        for admin_id in settings.ADMIN_IDS:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=digest_text,
                    parse_mode="HTML"
                )
                logger.info(f"Sent admin digest to {admin_id}")
            except Exception as e:
                logger.error(f"Failed to send digest to admin {admin_id}: {e}")
    except Exception as e:
        logger.error(f"Failed to generate admin digest: {e}")

async def send_marketing_digest(bot: Bot) -> None:
    """Send daily marketing digest to marketing group."""
    from config import settings as cfg
    if not cfg.MARKETING_GROUP_ID:
        return

    logger.info("Running marketing daily digest job")

    try:
        from services.marketing_analytics import get_daily_digest
        digest_text = await get_daily_digest()
        await bot.send_message(
            chat_id=cfg.MARKETING_GROUP_ID,
            text=digest_text
        )
        logger.info(f"Sent marketing digest to group {cfg.MARKETING_GROUP_ID}")
    except Exception as e:
        logger.error(f"Failed to send marketing digest: {e}")


async def send_trial_drip(bot: Bot) -> None:
    """Дожимающая цепочка для триальных пользователей.

    Отправляет 3 сообщения за 3 дня триала:
    - День 1 (через ~24ч): Напоминание попробовать ключевые фичи
    - День 2 (через ~48ч): Предупреждение "завтра закончится"
    - День 3 (через ~72ч): Финальное предложение со скидкой + downsell
    """
    from datetime import timedelta
    now = datetime.now()
    logger.info("Running trial drip check...")

    async for session in get_db():
        # Все активные триальные подписки (явный payment_source='trial')
        stmt = select(Subscription).where(
            and_(
                Subscription.is_active == True,  # noqa: E712
                Subscription.tier != "free",
                Subscription.expires_at.isnot(None),
                Subscription.payment_source == PAYMENT_SOURCE_TRIAL,
            )
        )
        subs = (await session.execute(stmt)).scalars().all()

        for sub in subs:
            if not sub.expires_at:
                continue

            remaining = sub.expires_at - now
            days_left = remaining.days
            hours_left = remaining.total_seconds() / 3600

            # Определяем, какое сообщение отправить
            # День 1: осталось 46-50 часов (прошло ~22-26ч из 72)
            # День 2: осталось 22-26 часов
            # День 3: осталось 0-4 часа

            msg = None
            drip_tag = None

            if 46 <= hours_left <= 50:
                drip_tag = "drip_day1"
                msg = (
                    "Привет 👋\n\n"
                    "Вопрос в лоб: <b>что ты ел сегодня на завтрак?</b>\n\n"
                    "Просто напиши ответ сюда — покажу КБЖУ. "
                    "Это займёт секунд 10.\n\n"
                    "<i>Например: «овсянка 200г и кофе»</i>"
                )

            elif 22 <= hours_left <= 26:
                drip_tag = "drip_day2"
                msg = (
                    "⏰ <b>Твой PRO заканчивается завтра!</b>\n\n"
                    "Через 24 часа ты потеряешь доступ к:\n"
                    "• 📸 Анализу фото еды\n"
                    "• 🧾 Сканеру чеков\n"
                    "• 👩‍⚕️ Нейро-нутрициологу\n\n"
                    "Чтобы сохранить всё это — оформи подписку 👇"
                )

            elif 0 <= hours_left <= 4:
                drip_tag = "drip_day3"
                msg = (
                    "🔒 <b>PRO закончился (или вот-вот...)</b>\n\n"
                    "Без подписки бот по-прежнему работает — ручной ввод текстом, вода, вес. "
                    "Но если хочешь вернуть <b>фото, голос и ИИ-гида</b>:\n\n"
                    "🚀 <b>Pro — 299 ₽/мес</b> (полный набор)\n"
                    "💡 <b>Basic — 199 ₽/мес</b> (голос + холодильник)\n\n"
                    "Выбери свой вариант 👇"
                )

            if msg and drip_tag:
                # Проверяем, не отправляли ли уже это сообщение
                from database.models import UserFeedback
                check_stmt = select(func.count()).select_from(UserFeedback).where(
                    and_(
                        UserFeedback.user_id == sub.user_id,
                        UserFeedback.feedback_type == drip_tag,
                    )
                )
                already_sent = (await session.execute(check_stmt)).scalar() or 0

                if already_sent > 0:
                    continue

                try:
                    from aiogram.utils.keyboard import InlineKeyboardBuilder
                    reply_markup = None
                    if drip_tag != "drip_day1":
                        # Day 2/3 — ведём на подписки
                        builder = InlineKeyboardBuilder()
                        builder.button(text="💎 Подписки", callback_data="show_subscriptions")
                        builder.adjust(1)
                        reply_markup = builder.as_markup()
                    # Day 1 — без кнопок: живой вопрос, юзер пишет ответ -> universal_input поймает

                    sent = await safe_send_message(
                        bot, sub.user_id,
                        text=msg,
                        parse_mode="HTML",
                        reply_markup=reply_markup
                    )

                    if sent:
                        fb = UserFeedback(
                            user_id=sub.user_id,
                            feedback_type=drip_tag,
                            answer=f"sent at {now.isoformat()}",
                        )
                        session.add(fb)
                        logger.info(f"Sent {drip_tag} to user {sub.user_id}")

                except Exception as e:
                    logger.error(f"Failed to send {drip_tag} to {sub.user_id}: {e}")

        await session.commit()
        break


async def send_first_log_nudge(bot: Bot) -> None:
    """Разово нуджит пользователей, завершивших онбординг 3+ часа назад, но не внёсших ни одного лога."""
    from datetime import timedelta
    from database.models import UserFeedback

    now = datetime.now()
    threshold = now - timedelta(hours=3)
    logger.info("Running first_log_nudge check...")

    async for session in get_db():
        stmt = (
            select(User)
            .join(UserSettings, User.id == UserSettings.user_id)
            .where(
                and_(
                    UserSettings.is_initialized == True,  # noqa: E712
                    User.created_at <= threshold,
                    User.is_blocked.is_not(True),
                )
            )
        )
        users = (await session.execute(stmt)).scalars().all()

        for user in users:
            logs_count = (await session.execute(
                select(func.count()).select_from(ConsumptionLog).where(
                    ConsumptionLog.user_id == user.id
                )
            )).scalar() or 0

            if logs_count > 0:
                continue

            already_sent = (await session.execute(
                select(func.count()).select_from(UserFeedback).where(
                    and_(
                        UserFeedback.user_id == user.id,
                        UserFeedback.feedback_type == "first_log_nudge",
                    )
                )
            )).scalar() or 0

            if already_sent > 0:
                continue

            name = user.first_name or "друг"

            sent = await safe_send_message(
                bot,
                user.id,
                text=(
                    f"{name}, привет 👋\n\n"
                    "Заметил — ты настроил профиль, но еду пока не записывал.\n\n"
                    "<b>Давай прямо сейчас:</b> напиши одной строкой, "
                    "что ел последним. Например:\n"
                    "<code>овсянка 200г</code>\n\n"
                    "Я посчитаю КБЖУ за 3 секунды."
                ),
                parse_mode="HTML",
            )

            if sent:
                session.add(UserFeedback(
                    user_id=user.id,
                    feedback_type="first_log_nudge",
                    answer=f"sent at {now.isoformat()}",
                ))
                logger.info(f"Sent first_log_nudge to user {user.id}")

        await session.commit()
        break


async def send_morning_reminder(bot: Bot) -> None:
    """Утреннее напоминание для пользователей, выбравших '⏰ Напомни в 8:00' при онбординге."""
    from database.models import UserFeedback

    now = datetime.now()
    logger.info("Running morning_reminder_v1 check...")

    async for session in get_db():
        pending = (await session.execute(
            select(UserFeedback).where(
                (UserFeedback.feedback_type == "morning_reminder_v1") &
                (UserFeedback.answer == "pending")
            )
        )).scalars().all()

        for fb in pending:
            try:
                sent = await safe_send_message(
                    bot, fb.user_id,
                    text=(
                        "☀️ Доброе утро!\n\n"
                        "Вот и 8 утра — самое время записать завтрак.\n\n"
                        "Напиши одной строкой что ел: например <code>яичница 2 яйца, кофе</code> — "
                        "я посчитаю КБЖУ за секунду ⚡"
                    ),
                    parse_mode="HTML",
                )
                fb.answer = f"sent at {now.isoformat()}" if sent else f"blocked at {now.isoformat()}"
                if sent:
                    logger.info(f"Sent morning_reminder_v1 to user {fb.user_id}")
            except Exception as e:
                logger.error(f"Failed morning_reminder to {fb.user_id}: {e}")
                fb.answer = f"failed: {str(e)[:100]}"

        if pending:
            await session.commit()
        break


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

    # 5. Curator Morning Summaries (Hourly check - sends based on curator_summary_time)
    scheduler.add_job(
        send_curator_summaries,
        CronTrigger(minute=0),  # Every hour at :00
        args=[bot],
        id="curator_summaries",
        replace_existing=True
    )

    # 3. Visual Nutrition Report (12:00 MSK)
    scheduler.add_job(
        run_daily_report,
        CronTrigger(hour=12, minute=0),
        id="visual_daily_report",
        replace_existing=True
    )

    # 4. Expire one-time subscriptions (every hour)
    scheduler.add_job(
        expire_subscriptions,
        CronTrigger(minute=30),  # Every hour at :30
        args=[bot],
        id="expire_subscriptions",
        replace_existing=True
    )

    # 6. Onboarding Reminders (every hour at :15)
    scheduler.add_job(
        send_onboarding_reminders,
        CronTrigger(minute=15),  # Every hour at :15
        args=[bot],
        id="onboarding_reminders",
        replace_existing=True
    )

    # 7. Admin Daily Digest (09:00 MSK)
    scheduler.add_job(
        send_admin_digest,
        CronTrigger(hour=9, minute=0),
        args=[bot],
        id="admin_digest",
        replace_existing=True
    )

    # 8. Marketing Daily Digest (09:05 MSK)
    scheduler.add_job(
        send_marketing_digest,
        CronTrigger(hour=9, minute=5),
        args=[bot],
        id="marketing_digest",
        replace_existing=True
    )

    # 9. Trial Drip — дожимающая цепочка для триальных юзеров (каждые 2 часа)
    scheduler.add_job(
        send_trial_drip,
        CronTrigger(minute=45, hour="*/2"),  # Каждые 2 часа в :45
        args=[bot],
        id="trial_drip",
        replace_existing=True
    )

    # 10. First Log Nudge — для пользователей без единого лога еды (каждые 2 часа)
    scheduler.add_job(
        send_first_log_nudge,
        CronTrigger(minute=20, hour="*/2"),  # Каждые 2 часа в :20
        args=[bot],
        id="first_log_nudge",
        replace_existing=True
    )

    # 11. Morning Reminder — для пользователей, нажавших "Напомни в 8:00" (08:00 MSK)
    scheduler.add_job(
        send_morning_reminder,
        CronTrigger(hour=8, minute=0),
        args=[bot],
        id="morning_reminder",
        replace_existing=True
    )

    scheduler.start()
    logger.info("📅 Reminder scheduler started (11 jobs)")

    return scheduler

