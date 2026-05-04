"""Tests for onboarding handlers."""
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from database.models import UserSettings
from handlers.onboarding import OnboardingStates, start_onboarding


@pytest.mark.asyncio
async def test_start_onboarding_new_user(db_session, mock_telegram_message, mock_fsm_context):
    """Test starting onboarding for new user."""
    # User doesn't have settings yet
    mock_fsm_context.set_state = AsyncMock()

    await start_onboarding(mock_telegram_message, mock_fsm_context)

    # Check that state was set (первый шаг онбординга — acquisition source)
    mock_fsm_context.set_state.assert_called_once_with(OnboardingStates.waiting_for_source)
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

    # Check that state was set (первый шаг онбординга — acquisition source)
    mock_fsm_context.set_state.assert_called_once_with(OnboardingStates.waiting_for_source)


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
    # Check that state was changed to age (NEW since mass linting/update)
    mock_fsm_context.set_state.assert_called_once_with(OnboardingStates.waiting_for_age)


@pytest.mark.asyncio
async def test_handle_age_input_valid(db_session, mock_telegram_message, mock_fsm_context):
    """Test age input with valid value."""
    from handlers.onboarding import handle_age_input

    mock_telegram_message.text = "25"
    mock_fsm_context.update_data = AsyncMock()
    mock_fsm_context.set_state = AsyncMock()

    await handle_age_input(mock_telegram_message, mock_fsm_context)

    # Check that age was saved
    mock_fsm_context.update_data.assert_called_once_with(age=25)
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

    # Check that state was changed to calorie confirmation (NEW step)
    mock_fsm_context.set_state.assert_called_once_with(OnboardingStates.waiting_for_calorie_confirmation)
    # state should NOT be cleared yet
    assert not mock_fsm_context.clear.called

@pytest.mark.asyncio
async def test_handle_goal_accept(
    db_session, mock_callback_query, mock_fsm_context, sample_user
):
    """Test accepting calculated goals during onboarding."""
    from handlers.onboarding import handle_goal_accept

    mock_callback_query.message.chat.id = sample_user.id
    mock_fsm_context.get_data = AsyncMock(
        return_value={
            "gender": "male", "age": 30, "height": 180, "weight": 80.0, "goal": "lose_weight",
            "pending_targets": {"calories": 2000, "protein": 150, "fat": 60, "carbs": 200}
        }
    )
    mock_fsm_context.clear = AsyncMock()
    mock_callback_query.message.delete = AsyncMock()
    mock_callback_query.message.answer = AsyncMock()

    with patch('handlers.onboarding.get_db') as mock_get_db:
        async def db_generator():
            yield db_session
        mock_get_db.return_value = db_generator()

        await handle_goal_accept(mock_callback_query, mock_fsm_context)

    # Check that state was cleared
    mock_fsm_context.clear.assert_called_once()
    mock_callback_query.answer.assert_called_once()
    # finish_onboarding_process делает 2 вызова answer: финальный текст + «горячий» вопрос
    assert mock_callback_query.message.answer.call_count == 2

    # Check that settings were saved
    stmt = select(UserSettings).where(UserSettings.user_id == sample_user.id)
    result = await db_session.execute(stmt)
    settings = result.scalar_one_or_none()
    assert settings is not None
    assert settings.gender == "male"
    assert settings.height == 180
    assert settings.weight == 80.0
    assert settings.goal == "lose_weight"
    assert settings.is_initialized is True









