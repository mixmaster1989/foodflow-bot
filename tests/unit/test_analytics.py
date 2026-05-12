import time
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from database.models import ProductEvent
from utils.analytics import log_event


@pytest.mark.asyncio
async def test_log_event_basic(db_session, sample_user):
    """Test basic event logging to database."""
    event_name = "test_event"
    payload = {"key": "value"}

    # We need to patch async_session in utils.analytics to use our test db_session
    with patch('utils.analytics.async_session') as mock_session_factory:
        mock_session_factory.return_value.__aenter__.return_value = db_session

        await log_event(sample_user.id, event_name, payload)

    # Verify in DB
    stmt = select(ProductEvent).where(ProductEvent.user_id == sample_user.id)
    result = await db_session.execute(stmt)
    event = result.scalar_one_or_none()

    assert event is not None
    assert event.event_name == event_name
    assert event.payload == payload

@pytest.mark.asyncio
async def test_first_time_log_logic(db_session, sample_user):
    """Test that first_time events are correctly triggered and time is calculated."""
    event_name = "food_logged"

    with patch('utils.analytics.async_session') as mock_session_factory:
        mock_session_factory.return_value.__aenter__.return_value = db_session

        # Log first time
        await log_event(sample_user.id, event_name, {"food": "apple"})

    # Check for two events: food_logged AND food_logged_first_time
    stmt = select(ProductEvent).where(ProductEvent.user_id == sample_user.id).order_by(ProductEvent.created_at.asc())
    result = await db_session.execute(stmt)
    events = result.scalars().all()

    event_names = [e.event_name for e in events]
    assert "food_logged" in event_names
    assert "food_logged_first_time" in event_names

    first_time_event = next(e for e in events if e.event_name == "food_logged_first_time")
    assert "seconds_since_signup" in first_time_event.payload
    assert first_time_event.payload["triggered_by"] == "food_logged"

@pytest.mark.asyncio
async def test_rage_back_detection(mock_fsm_context):
    """Test rage_back logic simulation in handlers."""
    # This logic is integrated in onboarding handler, but we test the detection principle here
    user_id = 12345

    # Mock data for first click
    mock_fsm_context.get_data = AsyncMock(return_value={"last_back_time": time.time() - 0.5})

    # Logic from handler:
    data = await mock_fsm_context.get_data()
    last_back = data.get("last_back_time", 0)
    now = time.time()

    is_rage = (now - last_back < 2.0)
    assert is_rage is True

@pytest.mark.asyncio
async def test_onboarding_abandoned_handler(db_session, mock_callback_query, mock_fsm_context, sample_user):
    """Test explicit onboarding abandonment handler."""
    from handlers.onboarding import handle_onboarding_cancel

    mock_callback_query.from_user.id = sample_user.id
    mock_fsm_context.get_state = AsyncMock(return_value="OnboardingStates:waiting_for_weight")
    mock_callback_query.message.edit_text = AsyncMock()

    with patch('utils.analytics.async_session') as mock_session_factory:
        mock_session_factory.return_value.__aenter__.return_value = db_session

        await handle_onboarding_cancel(mock_callback_query, mock_fsm_context)

    # Verify event in DB
    stmt = select(ProductEvent).where(
        ProductEvent.user_id == sample_user.id,
        ProductEvent.event_name == "onboarding_abandoned"
    )
    result = await db_session.execute(stmt)
    event = result.scalar_one_or_none()

    assert event is not None
    assert event.payload["step"] == "OnboardingStates:waiting_for_weight"
    mock_fsm_context.clear.assert_called_once()
