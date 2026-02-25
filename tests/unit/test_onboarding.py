"""Tests for onboarding handlers."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from database.models import UserSettings
from handlers.onboarding import OnboardingStates, start_onboarding
from sqlalchemy import select


@pytest.mark.asyncio
async def test_start_onboarding_new_user(db_session, mock_telegram_message, mock_fsm_context):
    """Test starting onboarding for new user."""
    # User doesn't have settings yet
    mock_fsm_context.set_state = AsyncMock()

    await start_onboarding(mock_telegram_message, mock_fsm_context)

    # Check that state was set
    mock_fsm_context.set_state.assert_called_once_with(OnboardingStates.waiting_for_gender)
    # Check that message was sent
    mock_telegram_message.answer.assert_called_once()


@pytest.mark.asyncio
async def test_start_onboarding_existing_user_not_initialized(
    db_session, mock_telegram_message, mock_fsm_context, sample_user
):
    """Test starting onboarding for user with settings but not initialized."""
    # Create settings but not initialized
    settings = UserSettings(user_id=sample_user.id, is_initialized=False)
    db_session.add(settings)
    await db_session.commit()

    mock_fsm_context.set_state = AsyncMock()

    await start_onboarding(mock_telegram_message, mock_fsm_context)

    # Check that state was set
    mock_fsm_context.set_state.assert_called_once_with(OnboardingStates.waiting_for_gender)


@pytest.mark.asyncio
async def test_handle_gender_selection(db_session, mock_callback_query, mock_fsm_context):
    """Test gender selection handler."""
    from handlers.onboarding import handle_gender_selection

    mock_callback_query.data = "onboarding_gender:male"
    mock_fsm_context.update_data = AsyncMock()
    mock_fsm_context.set_state = AsyncMock()

    await handle_gender_selection(mock_callback_query, mock_fsm_context)

    # Check that gender was saved
    mock_fsm_context.update_data.assert_called_once_with(gender="male")
    # Check that state was changed to height
    mock_fsm_context.set_state.assert_called_once_with(OnboardingStates.waiting_for_height)


@pytest.mark.asyncio
async def test_handle_height_input_valid(db_session, mock_telegram_message, mock_fsm_context):
    """Test height input with valid value."""
    from handlers.onboarding import handle_height_input

    mock_telegram_message.text = "175"
    mock_fsm_context.update_data = AsyncMock()
    mock_fsm_context.set_state = AsyncMock()

    await handle_height_input(mock_telegram_message, mock_fsm_context)

    # Check that height was saved
    mock_fsm_context.update_data.assert_called_once_with(height=175)
    # Check that state was changed to weight
    mock_fsm_context.set_state.assert_called_once_with(OnboardingStates.waiting_for_weight)


@pytest.mark.asyncio
async def test_handle_height_input_invalid(db_session, mock_telegram_message, mock_fsm_context):
    """Test height input with invalid value."""
    from handlers.onboarding import handle_height_input

    mock_telegram_message.text = "abc"
    mock_telegram_message.answer = AsyncMock()

    await handle_height_input(mock_telegram_message, mock_fsm_context)

    # Check that error message was sent
    mock_telegram_message.answer.assert_called_once()


@pytest.mark.asyncio
async def test_handle_weight_input_valid(db_session, mock_telegram_message, mock_fsm_context):
    """Test weight input with valid value."""
    from handlers.onboarding import handle_weight_input

    mock_telegram_message.text = "70.5"
    mock_fsm_context.update_data = AsyncMock()
    mock_fsm_context.set_state = AsyncMock()

    await handle_weight_input(mock_telegram_message, mock_fsm_context)

    # Check that weight was saved
    mock_fsm_context.update_data.assert_called_once_with(weight=70.5)
    # Check that state was changed to goal
    mock_fsm_context.set_state.assert_called_once_with(OnboardingStates.waiting_for_goal)


@pytest.mark.asyncio
async def test_handle_goal_selection_and_finish(
    db_session, mock_callback_query, mock_fsm_context, sample_user
):
    """Test goal selection and onboarding completion."""
    from handlers.onboarding import handle_goal_selection

    mock_callback_query.data = "onboarding_goal:lose_weight"
    mock_callback_query.from_user.id = sample_user.id
    mock_fsm_context.get_data = AsyncMock(
        return_value={"gender": "male", "height": 180, "weight": 80.0}
    )
    mock_fsm_context.clear = AsyncMock()
    mock_callback_query.message.delete = AsyncMock()
    mock_callback_query.message.answer = AsyncMock()

    await handle_goal_selection(mock_callback_query, mock_fsm_context)

    # Check that state was cleared
    mock_fsm_context.clear.assert_called_once()

    # Check that settings were saved
    async for session in db_session:
        stmt = select(UserSettings).where(UserSettings.user_id == sample_user.id)
        result = await session.execute(stmt)
        settings = result.scalar_one_or_none()
        assert settings is not None
        assert settings.gender == "male"
        assert settings.height == 180
        assert settings.weight == 80.0
        assert settings.goal == "lose_weight"
        assert settings.is_initialized is True
        break









