from datetime import date, datetime

import pytz
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from api.auth import CurrentUser, DBSession
from api.schemas import (
    ConsumptionLogCreate,
    ConsumptionLogRead,
    ConsumptionLogUpdate,
)
from database.models import ConsumptionLog

router = APIRouter()


@router.get("", response_model=list[ConsumptionLogRead])
async def list_consumption_logs(
    user: CurrentUser,
    session: DBSession,
    target_date: date | None = Query(None, alias="date"),
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
):
    """List consumption logs with optional date filtering."""
    stmt = select(ConsumptionLog).where(ConsumptionLog.user_id == user.id)

    if target_date:
        stmt = stmt.where(func.date(ConsumptionLog.date) == target_date)
    else:
        if from_date:
            stmt = stmt.where(func.date(ConsumptionLog.date) >= from_date)
        if to_date:
            stmt = stmt.where(func.date(ConsumptionLog.date) <= to_date)

    stmt = stmt.order_by(ConsumptionLog.date.desc()).limit(100)
    logs = (await session.execute(stmt)).scalars().all()

    return [ConsumptionLogRead.model_validate(log) for log in logs]


@router.post("", response_model=ConsumptionLogRead, status_code=201)
async def create_consumption_log(
    log_data: ConsumptionLogCreate,
    user: CurrentUser,
    session: DBSession,
):
    """Log food consumption (standard)."""
    msk_tz = pytz.timezone("Europe/Moscow")
    
    log_date = datetime.now(msk_tz).replace(tzinfo=None)
    if log_data.date:
        if log_data.date.tzinfo:
            log_date = log_data.date.astimezone(msk_tz).replace(tzinfo=None)
        else:
            log_date = log_data.date

    log = ConsumptionLog(
        user_id=user.id,
        product_name=log_data.product_name,
        calories=log_data.calories,
        protein=log_data.protein,
        fat=log_data.fat,
        carbs=log_data.carbs,
        fiber=log_data.fiber,
        date=log_date,
    )
    session.add(log)
    await session.commit()
    await session.refresh(log)
    return ConsumptionLogRead.model_validate(log)


@router.post("/manual", response_model=ConsumptionLogRead, status_code=201)
async def create_manual_log(
    log_data: ConsumptionLogCreate,
    user: CurrentUser,
    session: DBSession,
):
    """Manual log from Quick Log (formats name with weight)."""
    final_name = log_data.product_name
    if log_data.weight_g:
        final_name = f"{log_data.product_name} ({int(log_data.weight_g)}г)"

    msk_tz = pytz.timezone("Europe/Moscow")
    
    log_date = datetime.now(msk_tz).replace(tzinfo=None)
    if log_data.date:
        if log_data.date.tzinfo:
            log_date = log_data.date.astimezone(msk_tz).replace(tzinfo=None)
        else:
            log_date = log_data.date

    log = ConsumptionLog(
        user_id=user.id,
        product_name=final_name,
        base_name=log_data.product_name, # Save clean name too for grouping
        calories=log_data.calories,
        protein=log_data.protein,
        fat=log_data.fat,
        carbs=log_data.carbs,
        fiber=log_data.fiber,
        date=log_date,
    )
    session.add(log)
    await session.commit()
    await session.refresh(log)
    return ConsumptionLogRead.model_validate(log)


@router.delete("/{log_id}", status_code=204)
async def delete_consumption_log(log_id: int, user: CurrentUser, session: DBSession):
    """Delete a consumption log entry."""
    log = await session.get(ConsumptionLog, log_id)

    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    if log.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    await session.delete(log)
    await session.commit()


@router.patch("/{log_id}", response_model=ConsumptionLogRead)
async def update_consumption_log(
    log_id: int,
    log_data: ConsumptionLogUpdate,
    user: CurrentUser,
    session: DBSession,
):
    """Update a consumption log entry."""
    log = await session.get(ConsumptionLog, log_id)

    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    if log.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Update fields
    update_data = log_data.model_dump(exclude_unset=True)
    
    # Special handling for date to ensure consistency with timezone
    if "date" in update_data and update_data["date"]:
        msk_tz = pytz.timezone("Europe/Moscow")
        dt = update_data["date"]
        if dt.tzinfo:
            update_data["date"] = dt.astimezone(msk_tz).replace(tzinfo=None)
        else:
            update_data["date"] = dt

    for key, value in update_data.items():
        setattr(log, key, value)

    session.add(log)
    await session.commit()
    await session.refresh(log)
    return ConsumptionLogRead.model_validate(log)
