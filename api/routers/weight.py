from datetime import datetime

import pytz
from fastapi import APIRouter
from sqlalchemy import select

from api.auth import CurrentUser, DBSession
from api.schemas import WeightLogCreate, WeightLogRead
from database.models import UserSettings, WeightLog

router = APIRouter()


@router.get("", response_model=list[WeightLogRead])
async def list_weight_logs(user: CurrentUser, session: DBSession, limit: int = 30):
    """Get weight history."""
    stmt = (
        select(WeightLog)
        .where(WeightLog.user_id == user.id)
        .order_by(WeightLog.recorded_at.desc())
        .limit(limit)
    )
    logs = (await session.execute(stmt)).scalars().all()
    return [WeightLogRead.model_validate(log) for log in logs]


@router.post("", response_model=WeightLogRead, status_code=201)
async def log_weight(data: WeightLogCreate, user: CurrentUser, session: DBSession):
    """Log current weight."""
    msk_tz = pytz.timezone("Europe/Moscow")

    log = WeightLog(
        user_id=user.id,
        weight=data.weight,
        recorded_at=datetime.now(msk_tz).replace(tzinfo=None),
    )
    session.add(log)

    # Update current weight in settings
    settings_stmt = select(UserSettings).where(UserSettings.user_id == user.id)
    settings = (await session.execute(settings_stmt)).scalar_one_or_none()
    if settings:
        settings.weight = data.weight

    await session.commit()
    await session.refresh(log)
    return WeightLogRead.model_validate(log)
