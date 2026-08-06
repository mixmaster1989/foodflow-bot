"""Module for generating daily user reports.

Contains:
- generate_daily_report: Creates a text summary of daily nutrition logs.
- generate_curator_morning_summary: Aggregate ward stats for curator.
- generate_ward_ai_report: AI nutritionist analysis for a specific ward.
"""
import csv
import io
import logging
import os
from datetime import date, datetime, timedelta

from sqlalchemy import and_, func, select

from database.base import get_db
from database.models import (
    PAID_SOURCES,
    PAYMENT_SOURCE_STARS,
    PAYMENT_SOURCE_YOOKASSA,
    ConsumptionLog,
    ReferralEvent,
    Subscription,
    User,
    UserFeedback,
    UserSettings,
)
from utils.i18n import t, get_locale

logger = logging.getLogger(__name__)


async def generate_curator_morning_summary(curator_id: int) -> str | None:
    """Generate morning summary for curator with detailed food logs per ward.

    [CURATOR-3.1] Shows WHAT and WHEN each ward ate, not just totals.
    """
    yesterday = (datetime.now() - timedelta(days=1)).date()
    date_str = yesterday.strftime("%d.%m.%Y")

    async for session in get_db():
        # Get curator settings for locale
        curator_settings_stmt = select(UserSettings).where(UserSettings.user_id == curator_id)
        curator_settings = (await session.execute(curator_settings_stmt)).scalar_one_or_none()
        curator_locale = curator_settings.locale if curator_settings else "ru"

        # Get all wards
        stmt = select(User).where(User.curator_id == curator_id)
        wards = (await session.execute(stmt)).scalars().all()

        if not wards:
            return None

        active_wards = []
        inactive_wards = []

        for ward in wards:
            # Fetch logs for yesterday, ordered by time
            log_stmt = select(ConsumptionLog).where(
                ConsumptionLog.user_id == ward.id,
                func.date(ConsumptionLog.date) == yesterday
            ).order_by(ConsumptionLog.date)
            logs = (await session.execute(log_stmt)).scalars().all()

            # Get goals
            settings_stmt = select(UserSettings).where(UserSettings.user_id == ward.id)
            ward_settings = (await session.execute(settings_stmt)).scalar_one_or_none()
            goal_cal = ward_settings.calorie_goal if ward_settings and ward_settings.calorie_goal else 2000

            ward_name = ward.first_name or ward.username or f"ID:{ward.id}"

            if not logs:
                inactive_wards.append(ward_name)
                continue

            # Build detailed food list with timestamps
            total_cal = sum(log.calories or 0 for log in logs)
            total_prot = sum(log.protein or 0 for log in logs)
            total_fat = sum(log.fat or 0 for log in logs)
            total_carbs = sum(log.carbs or 0 for log in logs)
            total_fiber = sum(log.fiber or 0 for log in logs)

            # Status flags
            cal_ratio = total_cal / goal_cal if goal_cal > 0 else 0
            if cal_ratio < 0.5:
                status = "⚠️"  # Undereating
            elif cal_ratio > 1.2:
                status = "🔥"  # Overeating
            else:
                status = "✅"

            food_lines = []
            for log in logs:
                time_str = log.date.strftime("%H:%M")
                cal = int(log.calories or 0)
                food_lines.append(f"  <code>{time_str}</code> — {log.product_name} ({cal} {t('reports.unit_kcal', locale=curator_locale)})")

            active_wards.append({
                "name": ward_name,
                "status": status,
                "total_cal": int(total_cal),
                "total_prot": int(total_prot),
                "total_fat": int(total_fat),
                "total_carbs": int(total_carbs),
                "total_fiber": int(total_fiber),
                "goal_cal": int(goal_cal),
                "food_lines": food_lines,
                "log_count": len(logs)
            })

    # Build report text
    lines = [
        t("reports.curator_summary_title", locale=curator_locale, date=date_str),
        t("reports.curator_wards_count", locale=curator_locale, count=len(active_wards) + len(inactive_wards)),
    ]

    # Active wards with detailed logs
    if active_wards:
        lines.append(t("reports.curator_filled_diary", locale=curator_locale, count=len(active_wards)))
        for w in active_wards:
            cal_pct = int((w['total_cal'] / w['goal_cal']) * 100) if w['goal_cal'] > 0 else 0
            fiber_str = f"  {t('reports.curator_fiber_short', locale=curator_locale)}:{w['total_fiber']}" if w['total_fiber'] else ""
            lines.append(
                t(
                    "reports.curator_ward_row",
                    locale=curator_locale,
                    status=w['status'],
                    name=w['name'],
                    cal=w['total_cal'],
                    goal=w['goal_cal'],
                    unit_kcal=t("reports.unit_kcal", locale=curator_locale),
                    percent=cal_pct,
                    prot=w['total_prot'],
                    fat=w['total_fat'],
                    carbs=w['total_carbs'],
                    fiber_str=fiber_str
                )
            )
            for fl in w["food_lines"]:
                lines.append(fl)
            lines.append("")  # Empty line separator

    # Inactive wards
    if inactive_wards:
        lines.append(t("reports.curator_not_filled_diary", locale=curator_locale, count=len(inactive_wards)))
        lines.append(", ".join(inactive_wards))

    return "\n".join(lines)


async def generate_ward_ai_report(ward_id: int) -> dict | None:
    """Generate AI nutritionist report for a specific ward.

    [CURATOR-2.3] Sends FULL food log with timestamps to AI.
    Returns dict with 'text' (AI analysis) and 'prompt_data' for image card.
    """
    from services.daily_nutrition_report import (
        get_nutrition_report,
    )

    yesterday = (datetime.now() - timedelta(days=1)).date()

    async for session in get_db():
        # Get ward info
        ward = await session.get(User, ward_id)
        if not ward:
            return None
        ward_name = ward.first_name or ward.username or f"ID:{ward_id}"

        # Get settings (goals)
        settings_stmt = select(UserSettings).where(UserSettings.user_id == ward_id)
        ward_settings = (await session.execute(settings_stmt)).scalar_one_or_none()
        ward_locale = ward_settings.locale if ward_settings else "ru"
        goals = {
            "calories": ward_settings.calorie_goal if ward_settings and ward_settings.calorie_goal else 2000,
            "protein": ward_settings.protein_goal if ward_settings and ward_settings.protein_goal else 100,
            "fat": ward_settings.fat_goal if ward_settings and ward_settings.fat_goal else 70,
            "carbs": ward_settings.carb_goal if ward_settings and ward_settings.carb_goal else 250,
            "fiber": ward_settings.fiber_goal if ward_settings and ward_settings.fiber_goal else 30
        }

        # Get logs for yesterday WITH timestamps
        log_stmt = select(ConsumptionLog).where(
            and_(
                ConsumptionLog.user_id == ward_id,
                ConsumptionLog.date >= datetime.combine(yesterday, datetime.min.time()),
                ConsumptionLog.date < datetime.combine(yesterday + timedelta(days=1), datetime.min.time())
            )
        ).order_by(ConsumptionLog.date)
        logs = (await session.execute(log_stmt)).scalars().all()

    if not logs:
        return None

    # Build DETAILED food list for AI (time + product + weight + KBJU)
    total_cal = sum(log.calories or 0 for log in logs)
    total_prot = sum(log.protein or 0 for log in logs)
    total_fat = sum(log.fat or 0 for log in logs)
    total_carbs = sum(log.carbs or 0 for log in logs)
    total_fiber = sum(log.fiber or 0 for log in logs)

    food_list_lines = []
    for log in logs:
        time_str = log.date.strftime("%H:%M")
        weight_str = t("reports.curator_weight_format", locale=ward_locale, weight=int(log.weight), unit_g=t("reports.unit_grams_short", locale=ward_locale)) if getattr(log, 'weight', None) else ""
        fiber_str = t("reports.curator_fiber_format", locale=ward_locale, fiber=log.fiber, unit_g=t("reports.unit_grams_short", locale=ward_locale)) if log.fiber else ""
        food_list_lines.append(
            t(
                "reports.curator_food_line",
                locale=ward_locale,
                time=time_str,
                name=log.product_name,
                weight=weight_str,
                cal=int(log.calories or 0),
                unit_kcal=t("reports.unit_kcal", locale=ward_locale),
                prot=log.protein,
                fat=log.fat,
                carbs=log.carbs,
                unit_g=t("reports.unit_grams_short", locale=ward_locale),
                fiber=fiber_str
            )
        )

    food_list_text = "\n".join(food_list_lines) if food_list_lines else t("reports.curator_no_data", locale=ward_locale)

    # Prepare data for AI prompt
    prompt_data = {
        "date": yesterday.strftime("%d.%m.%Y"),
        "food_list": food_list_text,
        "total_cal": int(total_cal),
        "total_prot": round(total_prot, 1),
        "total_fat": round(total_fat, 1),
        "total_carb": round(total_carbs, 1)
    }

    # Get AI report
    ai_text = await get_nutrition_report(prompt_data)
    if not ai_text:
        ai_text = t("reports.ai_report_fallback")

    return {
        "ward_name": ward_name,
        "date": yesterday,
        "logs": logs,
        "totals": {
            "calories": total_cal,
            "protein": total_prot,
            "fat": total_fat,
            "carbs": total_carbs,
            "fiber": total_fiber
        },
        "goals": goals,
        "ai_text": ai_text
    }

async def generate_daily_report(user_id: int) -> str | None:
    """Generate daily nutrition report for a user."""
    today = datetime.now().date()

    async for session in get_db():
        # 1. Fetch User Settings (Goals)
        stmt_settings = select(UserSettings).where(UserSettings.user_id == user_id)
        settings = (await session.execute(stmt_settings)).scalar_one_or_none()

        # 2. Fetch Logs for Today
        stmt_logs = select(ConsumptionLog).where(
            ConsumptionLog.user_id == user_id,
            func.date(ConsumptionLog.date) == today
        )
        logs = (await session.execute(stmt_logs)).scalars().all()

        # --- CASE 0: No Activity ---
        if not logs:
            return t("reports.no_activity_title")

        # --- CASE 1: Activity Found ---

        # Calculate Totals
        total_cal = sum(log.calories for log in logs)
        total_prot = sum(log.protein for log in logs)
        total_fat = sum(log.fat for log in logs)
        total_carbs = sum(log.carbs for log in logs)
        total_fiber = sum(log.fiber for log in logs if log.fiber) # NEW: Calculate fiber

        # Goals (Corrected field names)
        goal_cal = settings.calorie_goal if settings and settings.calorie_goal else 2000.0
        goal_fiber = settings.fiber_goal if settings and settings.fiber_goal else 30.0 # NEW: Fiber goal


        # Calculations
        cal_percent = min((total_cal / goal_cal) * 100, 150) # Cap visual at 150%
        remaining_cal = max(goal_cal - total_cal, 0)

        fiber_percent = min((total_fiber / goal_fiber) * 100, 150)

        # Visual Bar Generator
        def make_bar(percent: float, length: int = 10) -> str:
            filled = int((percent / 100) * length)
            filled = min(filled, length)
            return "🟩" * filled + "⬜" * (length - filled)

        # Macro Distribution
        total_g = total_prot + total_fat + total_carbs
        if total_g > 0:
            p_pct = int((total_prot / total_g) * 100)
            f_pct = int((total_fat / total_g) * 100)
            c_pct = int((total_carbs / total_g) * 100)
        else:
            p_pct = f_pct = c_pct = 0

        date_str = datetime.now().strftime("%d %B")

        report = (
            t("reports.summary_title", date=date_str) +
            t("reports.calories_section", bar=make_bar(cal_percent), percent=int(cal_percent), total=int(total_cal), goal=int(goal_cal), remaining=int(remaining_cal)) +
            t("reports.fiber_section", bar=make_bar(fiber_percent), percent=int(fiber_percent), total=total_fiber, goal=int(goal_fiber)) +
            t("reports.balance_section", prot=int(total_prot), fat=int(total_fat), carbs=int(total_carbs), p_pct=p_pct, f_pct=f_pct, c_pct=c_pct, count=len(logs))
        )

        return report

    return None


async def generate_detailed_report(user_id: int, target_date: date = None) -> str | None:
    """Generate detailed daily report with timestamps for each meal."""
    if not target_date:
        target_date = datetime.now().date()

    async for session in get_db():
        stmt_logs = select(ConsumptionLog).where(
            ConsumptionLog.user_id == user_id,
            func.date(ConsumptionLog.date) == target_date
        ).order_by(ConsumptionLog.date)
        logs = (await session.execute(stmt_logs)).scalars().all()

        logger.info(f"📊 Detailed report generated for user {user_id} (date: {target_date}, items: {len(logs)})")

        date_str = target_date.strftime("%d.%m.%Y")
        if target_date == datetime.now().date():
            date_str += t("reports.unit_today")

        if not logs:
            return (
                t("reports.diary_title", date=date_str) +
                t("reports.diary_empty")
            )

        # Build detailed list
        lines = [t("reports.diary_title", date=date_str)]

        total_cal = 0
        total_prot = 0
        total_fat = 0
        total_carbs = 0
        total_fiber = 0

        for log in logs:
            time_h = log.date.hour
            time_formatted = log.date.strftime("%H:%M")

            # Period emoji
            if 5 <= time_h < 12:
                emoji = "🌅"
            elif 12 <= time_h < 17:
                emoji = "☀️"
            elif 17 <= time_h < 22:
                emoji = "🌆"
            else:
                emoji = "🌙"

            cal = int(log.calories) if log.calories else 0
            lines.append(t("reports.meal_line", emoji=emoji, time=time_formatted, name=log.product_name, cal=cal))

            total_cal += log.calories or 0
            total_prot += log.protein or 0
            total_fat += log.fat or 0
            total_carbs += log.carbs or 0
            total_fiber += log.fiber or 0

        lines.append(t("reports.total_day"))
        lines.append(t("reports.total_cal", total=int(total_cal)))

        macros_str = t("reports.macros_format", prot=int(total_prot), fat=int(total_fat), carbs=int(total_carbs))
        if total_fiber:
            macros_str += t("reports.macros_fiber_format", fiber=int(total_fiber))

        lines.append(macros_str)

        return "\n".join(lines)


async def send_daily_visual_report(user_id: int, bot, caption: str = None) -> bool:
    """Generate and send visual daily report card."""
    import logging

    from aiogram.types import BufferedInputFile

    from database.models import User
    from services.svg_renderer import draw_daily_card

    logger = logging.getLogger("reports.visual")
    today = datetime.now().date()

    try:
        async for session in get_db():
            # 1. Fetch User Data
            user = await session.get(User, user_id)
            user_name = user.first_name if user else t("reports.default_user")

            # 2. Fetch Settings (Goals)
            stmt_settings = select(UserSettings).where(UserSettings.user_id == user_id)
            settings = (await session.execute(stmt_settings)).scalar_one_or_none()

            goals = {
                "calories": settings.calorie_goal if settings and settings.calorie_goal else 2000,
                "protein": settings.protein_goal if settings and settings.protein_goal else 100,
                "fat": settings.fat_goal if settings and settings.fat_goal else 70,
                "carbs": settings.carb_goal if settings and settings.carb_goal else 250,
                "fiber": settings.fiber_goal if settings and settings.fiber_goal else 30,
                "water": settings.water_goal if settings else 2000
            }

            # 3. Fetch Logs for Today
            stmt_logs = select(ConsumptionLog).where(
                ConsumptionLog.user_id == user_id,
                func.date(ConsumptionLog.date) == today
            ).order_by(ConsumptionLog.date)
            logs = (await session.execute(stmt_logs)).scalars().all()

            if not logs:
                return False

            # 4. Calculate Totals
            total_metrics = {
                "calories": sum(log.calories or 0 for log in logs),
                "protein": sum(log.protein or 0 for log in logs),
                "fat": sum(log.fat or 0 for log in logs),
                "carbs": sum(log.carbs or 0 for log in logs),
                "fiber": sum(log.fiber or 0 for log in logs)
            }

            # 5. Generate Image
            image_bio = draw_daily_card(
                user_name=user_name,
                target_date=today,
                logs=logs,
                total_metrics=total_metrics,
                goals=goals
            )
            if image_bio is None:
                logger.error(f"draw_daily_card returned None for user {user_id}")
                return False

            # 6. Send to Telegram
            photo = BufferedInputFile(image_bio.getvalue(), filename="progress.png")
            await bot.send_photo(
                chat_id=user_id,
                photo=photo,
                caption=caption or t("reports.progress_caption"),
                parse_mode="HTML"
            )
            return True

    except Exception as e:
        logger.error(f"Failed to send visual report to {user_id}: {e}", exc_info=True)
        return False

    return False

async def generate_admin_daily_digest(locale: str = None) -> str:
    """Generate global daily statistics for administrators."""
    if not locale:
        locale = get_locale()
    yesterday = (datetime.now() - timedelta(days=1)).date()
    date_str = yesterday.strftime("%d.%m.%Y")

    async for session in get_db():
        # 1. New Users
        new_users_stmt = select(func.count(User.id)).where(func.date(User.created_at) == yesterday)
        new_users_count = (await session.execute(new_users_stmt)).scalar() or 0

        # 2. Total Logs Yesterday
        logs_stmt = select(func.count(ConsumptionLog.id)).where(func.date(ConsumptionLog.date) == yesterday)
        logs_count = (await session.execute(logs_stmt)).scalar() or 0

        # 3. Active Users (who logged at least once)
        active_users_stmt = select(func.count(func.distinct(ConsumptionLog.user_id))).where(func.date(ConsumptionLog.date) == yesterday)
        active_users_count = (await session.execute(active_users_stmt)).scalar() or 0

        # 4. Total Users
        total_users_stmt = select(func.count(User.id))
        total_users_count = (await session.execute(total_users_stmt)).scalar() or 0

        # 5. Feedback counts
        feedback_stmt = select(func.count(UserFeedback.id)).where(func.date(UserFeedback.created_at) == yesterday)
        feedback_count = (await session.execute(feedback_stmt)).scalar() or 0

        # 6. Referral signups
        ref_stmt = select(func.count(ReferralEvent.id)).where(
            and_(
                func.date(ReferralEvent.created_at) == yesterday,
                ReferralEvent.event_type == "signup"
            )
        )
        ref_signup_count = (await session.execute(ref_stmt)).scalar() or 0

        # 7. Payments / Revenue (only real paid sources: stars + yookassa)
        sub_stmt = select(Subscription).where(
            and_(
                func.date(Subscription.starts_at) == yesterday,
                Subscription.payment_source.in_(list(PAID_SOURCES)),
            )
        )
        subs = (await session.execute(sub_stmt)).scalars().all()

        pays_rub = 0
        pays_stars = 0
        rev_rub = 0
        rev_stars = 0

        # Prices from handlers/payments.py (Basic, Pro, Curator)
        prices_rub = {"basic": 199, "pro": 299, "curator": 499}
        prices_stars = {"basic": 130, "pro": 200, "curator": 350}

        for s in subs:
            if s.payment_source == PAYMENT_SOURCE_STARS:
                pays_stars += 1
                rev_stars += prices_stars.get(s.tier, 0)
            elif s.payment_source == PAYMENT_SOURCE_YOOKASSA:
                pays_rub += 1
                rev_rub += prices_rub.get(s.tier, 0)

        # 8. Database size (using absolute path if possible)
        try:
            # Common path in the project root
            db_path = '/home/user1/foodflow-bot_new/foodflow.db'
            if not os.path.exists(db_path):
                db_path = './foodflow.db' # Fallback
            db_size = os.path.getsize(db_path) / (1024 * 1024)
        except Exception:
            db_size = 0

        break

    # Calculations
    active_percent = (active_users_count / total_users_count * 100) if total_users_count > 0 else 0

    report = (
        t("reports.admin_digest_title", locale=locale, date=date_str) +
        t("reports.admin_users_header", locale=locale) +
        t("reports.admin_users_new", locale=locale, count=new_users_count, ref=ref_signup_count) +
        t("reports.admin_users_total", locale=locale, count=total_users_count) +
        t("reports.admin_activity_header", locale=locale) +
        t("reports.admin_activity_dau", locale=locale, count=active_users_count, percent=active_percent) +
        t("reports.admin_activity_logs", locale=locale, count=logs_count) +
        t("reports.admin_activity_feedback", locale=locale, count=feedback_count) +
        t("reports.admin_sales_header", locale=locale) +
        t("reports.admin_sales_rub", locale=locale, rev=rev_rub, pays=pays_rub) +
        t("reports.admin_sales_stars", locale=locale, rev=rev_stars, pays=pays_stars) +
        t("reports.admin_system_header", locale=locale) +
        t("reports.admin_system_db", locale=locale, size=db_size)
    )

    try:
        from content_factory.guerrilla.metrics import format_guerrilla_daily_digest_html

        guerrilla_block = format_guerrilla_daily_digest_html(yesterday)
        if guerrilla_block:
            report = f"{report}\n{guerrilla_block}\n"
    except Exception as e:
        logger.error("Guerrilla daily digest failed: %s", e, exc_info=True)
        report = report + t("reports.admin_guerrilla_failed", locale=locale, error=type(e).__name__)

    return report

async def generate_admin_stats_csv(days: int = 30) -> io.BytesIO:
    """Generate a CSV history of daily statistics for export.
    
    Includes new users, active users, logs, and estimated revenue per day.
    """
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "Date", "New Users", "Ref Signups", "Active Users",
        "Food Logs", "Feedback", "Sales RUB", "Rev RUB",
        "Sales Stars", "Rev Stars"
    ])

    prices_rub = {"basic": 199, "pro": 299, "curator": 499}
    prices_stars = {"basic": 130, "pro": 200, "curator": 350}

    async for session in get_db():
        for i in range(days):
            target_date = (datetime.now() - timedelta(days=i+1)).date()

            # Metrics
            nu = (await session.execute(select(func.count(User.id)).where(func.date(User.created_at) == target_date))).scalar() or 0
            ref = (await session.execute(select(func.count(ReferralEvent.id)).where(and_(func.date(ReferralEvent.created_at) == target_date, ReferralEvent.event_type == "signup")))).scalar() or 0
            au = (await session.execute(select(func.count(func.distinct(ConsumptionLog.user_id))).where(func.date(ConsumptionLog.date) == target_date))).scalar() or 0
            lc = (await session.execute(select(func.count(ConsumptionLog.id)).where(func.date(ConsumptionLog.date) == target_date))).scalar() or 0
            fc = (await session.execute(select(func.count(UserFeedback.id)).where(func.date(UserFeedback.created_at) == target_date))).scalar() or 0

            # Payments (only real paid sources: stars + yookassa)
            subs = (await session.execute(select(Subscription).where(and_(func.date(Subscription.starts_at) == target_date, Subscription.payment_source.in_(list(PAID_SOURCES)))))).scalars().all()

            p_rub = 0
            p_xtr = 0
            r_rub = 0
            r_xtr = 0
            for s in subs:
                if s.payment_source == PAYMENT_SOURCE_STARS:
                    p_xtr += 1
                    r_xtr += prices_stars.get(s.tier, 0)
                elif s.payment_source == PAYMENT_SOURCE_YOOKASSA:
                    p_rub += 1
                    r_rub += prices_rub.get(s.tier, 0)

            writer.writerow([
                target_date.strftime("%Y-%m-%d"), nu, ref, au, lc, fc, p_rub, r_rub, p_xtr, r_xtr
            ])

        break

    # Convert to bytes for Telegram send_document
    output.seek(0)
    byte_output = io.BytesIO(output.getvalue().encode('utf-8'))
    return byte_output
