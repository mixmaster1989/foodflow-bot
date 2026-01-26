"""Reports router for FoodFlow API."""
from datetime import date, datetime

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from api.auth import DBSession, CurrentUser
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
    if not target_date:
        target_date = datetime.utcnow().date()
    
    # Fetch logs
    stmt = select(ConsumptionLog).where(
        ConsumptionLog.user_id == user.id,
        func.date(ConsumptionLog.date) == target_date,
    )
    logs = (await session.execute(stmt)).scalars().all()
    
    # Calculate totals
    total_calories = sum(l.calories for l in logs) if logs else 0
    total_protein = sum(l.protein for l in logs) if logs else 0
    total_fat = sum(l.fat for l in logs) if logs else 0
    total_carbs = sum(l.carbs for l in logs) if logs else 0
    total_fiber = sum(l.fiber for l in logs if l.fiber) if logs else 0
    
    # Get goals
    settings_stmt = select(UserSettings).where(UserSettings.user_id == user.id)
    settings = (await session.execute(settings_stmt)).scalar_one_or_none()
    
    calorie_goal = settings.calorie_goal if settings else 2000
    fiber_goal = settings.fiber_goal if settings else 30
    
    return DailyReport(
        date=target_date.isoformat(),
        calories_consumed=round(total_calories, 1),
        calories_goal=calorie_goal,
        protein=round(total_protein, 1),
        fat=round(total_fat, 1),
        carbs=round(total_carbs, 1),
        fiber=round(total_fiber, 1),
        fiber_goal=fiber_goal,
        meals_count=len(logs),
    )
