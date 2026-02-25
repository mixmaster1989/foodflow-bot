
from unittest.mock import AsyncMock, patch

import pytest

from handlers import i_ate


@pytest.mark.asyncio
async def test_i_ate_process_shows_confirmation():
    """Test that i_ate_process sets state to confirmation instead of saving."""
    # Setup mocks
    message = AsyncMock()
    state = AsyncMock()
    status_msg = AsyncMock()
    message.answer.return_value = status_msg

    # Mock message data
    message.text = "Apple"
    message.from_user.id = 12345

    # Mock NormalizationService response
    mock_result = {
        "name": "Apple",
        "calories": 50,
        "protein": 0.5,
        "fat": 0.2,
        "carbs": 14,
        "weight_grams": 100,
        "weight_missing": False
    }

    with patch('handlers.i_ate.NormalizationService.analyze_food_intake', return_value=mock_result), \
         patch('handlers.i_ate.show_confirmation_interface') as mock_show_confirm:

        await i_ate.i_ate_process(message, state)

        # Verify we updated state with pending_product
        state.update_data.assert_called()
        call_args = state.update_data.call_args[1]
        assert 'pending_product' in call_args
        assert call_args['pending_product']['name'] == "Apple (100г)"

        # Verify we called show_confirmation_interface
        mock_show_confirm.assert_called_once()

@pytest.mark.asyncio
async def test_save_macro_value_updates_state():
    """Test that manual macro edit updates the pending_product correctly."""
    message = AsyncMock()
    state = AsyncMock()

    message.text = "200" # User enters 200 kcal

    # Current state has product with 100 kcal
    current_data = {
        "current_edit_field": "calories100",
        "pending_product": {"name": "Test Food", "calories100": 100}
    }
    state.get_data.return_value = current_data

    with patch('handlers.i_ate.show_confirmation_interface'):
        await i_ate.save_macro_value(message, state)

        # Verify update_data was called with new calorie value
        state.update_data.assert_called()
        # We need to check that the SPECIFIC arg passed has calories100 = 200.0
        # Since update_data merges, we check the call arguments.
        updated_product = state.update_data.call_args[1]['pending_product']
        assert updated_product['calories100'] == 200.0
