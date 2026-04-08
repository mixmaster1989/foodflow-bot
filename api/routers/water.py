"""Water tracking router for FoodFlow API."""
from datetime import date, datetime

import pytz
from fastapi import APIRouter, Query
from sqlalchemy import func, select

from api.auth import CurrentUser, DBSession
from api.schemas import WaterLogCreate, WaterLogRead
from database.models import WaterLog

router = APIRouter()


@router.get("", response_model=list[WaterLogRead])
async def list_water_logs(
    user: CurrentUser,
    session: DBSession,
    target_date: date | None = Query(None, alias="date"),
):
    """List water logs for a specific day (defaults to today)."""
    msk_tz = pytz.timezone("Europe/Moscow")

    if not target_date:
        target_date = datetime.now(msk_tz).date()

    stmt = (
        select(WaterLog)
        .where(
            WaterLog.user_id == user.id,
            func.date(WaterLog.date) == target_date,
        )
        .order_by(WaterLog.date.asc())
    )
    logs = (await session.execute(stmt)).scalars().all()

    return [WaterLogRead.model_validate(log) for log in logs]


@router.post("", response_model=WaterLogRead, status_code=201)
async def log_water(data: WaterLogCreate, user: CurrentUser, session: DBSession):
    """Log water intake."""
    msk_tz = pytz.timezone("Europe/Moscow")
    log = WaterLog(
        user_id=user.id,
        amount_ml=data.amount_ml,
        date=datetime.now(msk_tz).replace(tzinfo=None),
    )
    session.add(log)
    await session.commit()
    await session.refresh(log)
    return WaterLogRead.model_validate(log)


@router.delete("/{log_id}", status_code=204)
async def delete_water_log(log_id: int, user: CurrentUser, session: DBSession):
    """Delete a water log entry."""
    log = await session.get(WaterLog, log_id)

    if not log or log.user_id != user.id:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Log not found or access denied")

    await session.delete(log)
    await session.commit()
