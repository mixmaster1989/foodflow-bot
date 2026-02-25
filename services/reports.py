"""Module for generating daily user reports.

Contains:
- generate_daily_report: Creates a text summary of daily nutrition logs.
"""
import logging
from datetime import date, datetime

from sqlalchemy import func, select

from database.base import get_db
from database.models import ConsumptionLog, UserSettings

logger = logging.getLogger(__name__)

# TODO [CURATOR-2.3]: Add generate_ward_report(ward_id) for curator to view ward's stats
# TODO [CURATOR-3.1]: Add generate_curator_morning_summary(curator_id) for aggregate ward stats

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
            return (
                "🌙 <b>Итоги дня</b>\n\n"
                "Сегодня вы ничего не записали в дневник. 😔\n"
                "А ведь здесь мог быть красивый отчет о ваших успехах!\n\n"
                "<i>Попробуйте завтра записать хотя бы завтрак — это затягивает!</i> ✨"
            )

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
            f"📊 <b>Сводка за сегодня</b>\n"
            f"<i>{date_str}</i>\n\n"

            f"🔥 <b>Калории</b>\n"
            f"{make_bar(cal_percent)} {int(cal_percent)}%\n"
            f"Потреблено: <b>{int(total_cal)}</b> / {int(goal_cal)}\n"
            f"Осталось: <b>{int(remaining_cal)}</b>\n\n"

            f"🥬 <b>Клетчатка</b>\n"
            f"{make_bar(fiber_percent)} {int(fiber_percent)}%\n"
            f"Съедено: <b>{total_fiber:.1f}г</b> / {int(goal_fiber)}г\n\n"

            f"🧬 <b>БЖУ (Баланс)</b>\n"
            f"🔵 Белки: {int(total_prot)}г ({p_pct}%)\n"
            f"🟡 Жиры: {int(total_fat)}г ({f_pct}%)\n"
            f"🟠 Углеводы: {int(total_carbs)}г ({c_pct}%)\n\n"

            f"📝 Записей в дневнике: {len(logs)}"
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
            date_str += " (Сегодня)"

        if not logs:
            return (
                f"📋 <b>Дневник за {date_str}</b>\n\n"
                "Записей не обнаружено. Чистый холст! 🎨"
            )

        # Build detailed list
        lines = [f"📋 <b>Дневник за {date_str}</b>\n"]

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
            lines.append(f"{emoji} <code>{time_formatted}</code> — {log.product_name} — <b>{cal}</b> ккал")

            total_cal += log.calories or 0
            total_prot += log.protein or 0
            total_fat += log.fat or 0
            total_carbs += log.carbs or 0
            total_fiber += log.fiber or 0

        lines.append("\n<b>Итого за день:</b>")
        lines.append(f"🔥 <b>{int(total_cal)}</b> ккал")

        macros = [
            f"🥩 Б: <b>{int(total_prot)}</b>г",
            f"🥑 Ж: <b>{int(total_fat)}</b>г",
            f"🍞 У: <b>{int(total_carbs)}</b>г"
        ]
        if total_fiber:
            macros.append(f"🥬 Кл: <b>{int(total_fiber)}</b>г")

        lines.append(" | ".join(macros))

        return "\n".join(lines)


async def send_daily_visual_report(user_id: int, bot) -> bool:
    """Generate and send visual daily report card."""
    import logging

    from aiogram.types import BufferedInputFile

    from database.models import User
    from services.image_renderer import draw_daily_card

    logger = logging.getLogger("reports.visual")
    today = datetime.now().date()

    try:
        async for session in get_db():
            # 1. Fetch User Data
            user = await session.get(User, user_id)
            user_name = user.first_name if user else "Пользователь"

            # 2. Fetch Settings (Goals)
            stmt_settings = select(UserSettings).where(UserSettings.user_id == user_id)
            settings = (await session.execute(stmt_settings)).scalar_one_or_none()

            goals = {
                "calories": settings.calorie_goal if settings and settings.calorie_goal else 2000,
                "protein": settings.protein_goal if settings and settings.protein_goal else 100,
                "fat": settings.fat_goal if settings and settings.fat_goal else 70,
                "carbs": settings.carb_goal if settings and settings.carb_goal else 250,
                "fiber": settings.fiber_goal if settings and settings.fiber_goal else 30
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

            # 6. Send to Telegram
            photo = BufferedInputFile(image_bio.getvalue(), filename="progress.png")
            await bot.send_photo(
                chat_id=user_id,
                photo=photo,
                caption="📈 <b>Ваш прогресс на текущий момент</b>",
                parse_mode="HTML"
            )
            return True

    except Exception as e:
        logger.error(f"Failed to send visual report to {user_id}: {e}", exc_info=True)
        return False

    return False
