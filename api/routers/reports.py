from datetime import date, datetime

import pytz
from fastapi import APIRouter, Query
from sqlalchemy import func, select

from api.auth import CurrentUser, DBSession
from api.schemas import DailyReport
from database.models import ConsumptionLog, UserSettings

router = APIRouter()


@router.get("/daily", response_model=DailyReport)
async def get_daily_report(
    user: CurrentUser,
    session: DBSession,
    target_date: date | None = Query(None, alias="date"),
):
    """Get daily nutrition summary."""
    msk_tz = pytz.timezone("Europe/Moscow")

    if not target_date:
        target_date = datetime.now(msk_tz).date()

    # Fetch logs
    stmt = select(ConsumptionLog).where(
        ConsumptionLog.user_id == user.id,
        func.date(ConsumptionLog.date) == target_date,
    )
    logs = (await session.execute(stmt)).scalars().all()

    # Calculate totals
    total_calories = sum(log.calories for log in logs) if logs else 0
    total_protein = sum(log.protein for log in logs) if logs else 0
    total_fat = sum(log.fat for log in logs) if logs else 0
    total_carbs = sum(log.carbs for log in logs) if logs else 0
    total_fiber = sum(log.fiber for log in logs if log.fiber) if logs else 0

    # Get goals
    settings_stmt = select(UserSettings).where(UserSettings.user_id == user.id)
    settings = (await session.execute(settings_stmt)).scalar_one_or_none()

    calorie_goal = settings.calorie_goal if settings else 2000
    protein_goal = settings.protein_goal if settings else 150
    fat_goal = settings.fat_goal if settings else 70
    carb_goal = settings.carb_goal if settings else 250
    fiber_goal = settings.fiber_goal if settings else 30

    return DailyReport(
        date=target_date.isoformat(),
        calories_consumed=total_calories,
        calories_goal=calorie_goal,
        protein=total_protein,
        protein_goal=protein_goal,
        fat=total_fat,
        fat_goal=fat_goal,
        carbs=total_carbs,
        carb_goal=carb_goal,
        fiber=total_fiber,
        fiber_goal=fiber_goal,
        meals_count=len(logs),
    )
