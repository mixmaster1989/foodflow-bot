from datetime import datetime
from typing import Any

from sqlalchemy import func, select

from database.base import async_session
from database.models import ConsumptionLog, ProductEvent, User, WaterLog, WeightLog


async def log_event(user_id: int, event_name: str, payload: dict[str, Any] | None = None):
    """
    Logs a granular product event to the database.
    """
    async with async_session() as session:
        event = ProductEvent(
            user_id=user_id,
            event_name=event_name,
            payload=payload
        )
        session.add(event)

        # Specific logic for one-time events (first_time actions)
        if event_name in ["weight_logged", "water_logged", "food_logged", "vision_used"]:
            await check_and_log_first_time(session, user_id, event_name)

        await session.commit()

async def check_and_log_first_time(session, user_id: int, event_name: str):
    """
    Checks if this is the first time the user is performing this action
    and logs a special 'first_time' event if so.
    """
    mapping = {
        "weight_logged": ("weight_logged_first_time", WeightLog),
        "water_logged": ("water_logged_first_time", WaterLog),
        "food_logged": ("food_logged_first_time", ConsumptionLog),
        "vision_used": ("vision_first_used", ProductEvent) # for vision we check product_events itself
    }

    target_event, model = mapping.get(event_name, (None, None))
    if not target_event:
        return

    # Check if a 'first_time' event already exists for this user
    existing = await session.execute(
        select(ProductEvent).where(
            ProductEvent.user_id == user_id,
            ProductEvent.event_name == target_event
        )
    )
    if existing.scalars().first():
        return

    # If it's the first time, log it
    user_res = await session.execute(select(User).where(User.id == user_id))
    user = user_res.scalar()

    payload = {"triggered_by": event_name}
    if user:
        seconds_since_signup = int((datetime.now() - user.created_at).total_seconds())
        payload["seconds_since_signup"] = seconds_since_signup

    first_event = ProductEvent(
        user_id=user_id,
        event_name=target_event,
        payload=payload
    )
    session.add(first_event)

    # Check for habit_achieved (3+ logs in 7 days)
    if event_name == "food_logged":
        await check_habit_achieved(session, user_id)

async def check_habit_achieved(session, user_id: int):
    """
    Checks if the user has logged 3+ meals and logs 'habit_achieved'.
    """
    # Check if already achieved
    existing = await session.execute(
        select(ProductEvent).where(
            ProductEvent.user_id == user_id,
            ProductEvent.event_name == "habit_achieved"
        )
    )
    if existing.scalars().first():
        return

    # Count logs
    count_res = await session.execute(
        select(func.count(ConsumptionLog.id)).where(ConsumptionLog.user_id == user_id)
    )
    count = count_res.scalar()

    if count >= 3:
        # Also check if it's within 7 days of signup
        user_res = await session.execute(select(User).where(User.id == user_id))
        user = user_res.scalar()
        if user and (datetime.now() - user.created_at).days <= 7:
            session.add(ProductEvent(
                user_id=user_id,
                event_name="habit_achieved",
                payload={"total_logs": count}
            ))
