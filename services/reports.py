"""Module for generating daily user reports.

Contains:
- generate_daily_report: Creates a text summary of daily nutrition logs.
"""
from datetime import datetime
from sqlalchemy import select, func
from database.base import get_db
from database.models import ConsumptionLog, UserSettings

# TODO [CURATOR-2.3]: Add generate_ward_report(ward_id) for curator to view ward's stats
# TODO [CURATOR-3.1]: Add generate_curator_morning_summary(curator_id) for aggregate ward stats

async def generate_daily_report(user_id: int) -> str | None:
    """Generate daily nutrition report for a user."""
    today = datetime.utcnow().date()
    
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
        total_cal = sum(l.calories for l in logs)
        total_prot = sum(l.protein for l in logs)
        total_fat = sum(l.fat for l in logs)
        total_carbs = sum(l.carbs for l in logs)
        total_fiber = sum(l.fiber for l in logs if l.fiber) # NEW: Calculate fiber

        # Goals (Corrected field names)
        goal_cal = settings.calorie_goal if settings and settings.calorie_goal else 2000.0
        goal_fiber = settings.fiber_goal if settings and settings.fiber_goal else 30.0 # NEW: Fiber goal
        
        goal_prot = settings.protein_goal if settings and settings.protein_goal else 100.0
        goal_fat = settings.fat_goal if settings and settings.fat_goal else 70.0
        goal_carbs = settings.carb_goal if settings and settings.carb_goal else 250.0

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


async def generate_detailed_report(user_id: int) -> str | None:
    """Generate detailed daily report with timestamps for each meal."""
    today = datetime.utcnow().date()
    
    async for session in get_db():
        stmt_logs = select(ConsumptionLog).where(
            ConsumptionLog.user_id == user_id,
            func.date(ConsumptionLog.date) == today
        ).order_by(ConsumptionLog.date)
        logs = (await session.execute(stmt_logs)).scalars().all()
        
        if not logs:
            return (
                "📋 <b>Подробная сводка</b>\n\n"
                "Сегодня пока ничего не записано.\n"
                "Отправьте фото еды, чтобы начать! 📸"
            )
        
        # Build detailed list
        lines = ["📋 <b>Подробная сводка за сегодня</b>\n"]
        
        total_cal = 0
        total_prot = 0
        total_fat = 0
        total_carbs = 0
        
        for log in logs:
            # Adjust for Moscow timezone (+3)
            time_str = (log.date.hour + 3) % 24
            time_formatted = f"{time_str:02d}:{log.date.minute:02d}"
            
            cal = int(log.calories) if log.calories else 0
            lines.append(f"🕐 <b>{time_formatted}</b> — {log.product_name} — {cal} ккал")
            
            total_cal += log.calories or 0
            total_prot += log.protein or 0
            total_fat += log.fat or 0
            total_carbs += log.carbs or 0
        
        lines.append("\n━━━━━━━━━━━")
        lines.append(f"<b>Итого:</b> {int(total_cal)} ккал | Б: {int(total_prot)}г | Ж: {int(total_fat)}г | У: {int(total_carbs)}г")
        
        return "\n".join(lines)
    
    return None
