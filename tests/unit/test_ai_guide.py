import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from database.models import UserSettings, ConsumptionLog, WaterLog
from services.ai_guide import AIGuideService

@pytest.mark.asyncio
async def test_get_water_advice_no_last_food(mocker):
    """Test get_water_advice when there is no ConsumptionLog."""
    session_mock = AsyncMock()
    
    # Mock settings return
    mock_settings = UserSettings(user_id=1, guide_active_until=datetime.now() + timedelta(days=1))
    mock_settings.guide_config = {"personality": "hard", "answers": {}}
    
    # Mock execute results
    # First execute: settings
    # Second execute: today's water sum
    # Third execute: last food (ConsumptionLog)
    
    mock_settings_result = MagicMock()
    mock_settings_result.scalar_one_or_none.return_value = mock_settings
    
    mock_water_result = MagicMock()
    mock_water_result.scalar.return_value = 500
    
    mock_food_result = MagicMock()
    mock_food_result.scalar_one_or_none.return_value = None  # No food
    
    session_mock.execute.side_effect = [mock_settings_result, mock_water_result, mock_food_result]
    
    mock_ai = mocker.patch("services.ai_guide.AIService.get_completion", new_callable=AsyncMock)
    mock_ai.return_value = "Mocked Response"
    
    # Patch save_to_history to avoid DB logic
    mocker.patch("services.ai_guide.AIGuideService.save_to_history", new_callable=AsyncMock)
    mocker.patch("services.ai_guide.AIGuideService.check_and_compress", new_callable=AsyncMock)

    response = await AIGuideService.get_water_advice(1, 250, session_mock)
    
    assert response == "Mocked Response"
    # Verify the prompt string
    prompt = mock_ai.call_args[0][0]
    assert "[hard]: жестко отругай" in prompt
    assert "[soft]: ласково и с заботой" in prompt
    assert "[direct]: сухо констатируй" in prompt
    assert "Сегодня еще не ел" in prompt

from datetime import timedelta

@pytest.mark.asyncio
async def test_get_water_advice_with_food(mocker):
    """Test get_water_advice when ConsumptionLog has product_name (fixing the previous AttributeError)."""
    session_mock = AsyncMock()
    
    mock_settings = UserSettings(user_id=1, guide_active_until=datetime.now() + timedelta(days=1))
    mock_settings.guide_config = {"personality": "soft", "answers": {}}
    
    mock_settings_result = MagicMock()
    mock_settings_result.scalar_one_or_none.return_value = mock_settings
    
    mock_water_result = MagicMock()
    mock_water_result.scalar.return_value = 1000
    
    # Mocking ConsumptionLog
    mock_food = ConsumptionLog(id=1, user_id=1, product_name="Пицца", calories=800)
    mock_food_result = MagicMock()
    mock_food_result.scalar_one_or_none.return_value = mock_food
    
    session_mock.execute.side_effect = [mock_settings_result, mock_water_result, mock_food_result]
    
    mock_ai = mocker.patch("services.ai_guide.AIService.get_completion", new_callable=AsyncMock)
    mock_ai.return_value = "Mocked Response Soft"
    
    mocker.patch("services.ai_guide.AIGuideService.save_to_history", new_callable=AsyncMock)
    mocker.patch("services.ai_guide.AIGuideService.check_and_compress", new_callable=AsyncMock)

    response = await AIGuideService.get_water_advice(1, 500, session_mock)
    
    assert response == "Mocked Response Soft"
    prompt = mock_ai.call_args[0][0]
    
    # Ensure ORM bug is fixed (product_name is correctly injected into last_food_desc)
    assert "Пицца (800" in prompt
    assert "ПЕРСОНАЖ: soft" in prompt

@pytest.mark.asyncio
async def test_get_contextual_advice_presets(mocker):
    """Test get_contextual_advice correctly loads and injects the 3 personality presets."""
    session_mock = AsyncMock()
    
    mock_settings = UserSettings(user_id=1, guide_active_until=datetime.now() + timedelta(days=1))
    mock_settings.guide_config = {"personality": "direct", "answers": {}}
    mock_settings.calorie_goal = 2000
    
    # 1. Settings (scalar_one_or_none)
    mock_settings_result = MagicMock()
    mock_settings_result.scalar_one_or_none.return_value = mock_settings
    
    # 2. Food totals (scalars.all)
    mock_food_totals = MagicMock()
    mock_food_totals.scalars().all.return_value = []
    
    # 3. Water total (scalar)
    mock_water_result = MagicMock()
    mock_water_result.scalar.return_value = 0
    
    # 4. History ConsumptionLog (scalars.all)
    mock_history_desc = MagicMock()
    mock_history_desc.scalars().all.return_value = []
    
    # 5. Used Features (scalars.all)
    mock_used_features = MagicMock()
    mock_used_features.scalars().all.return_value = ["weight"] # So unused are fridge, etc.
    
    # 6. Fridge (scalars.all)
    mock_fridge_result = MagicMock()
    mock_fridge_result.scalars().all.return_value = []

    session_mock.execute.side_effect = [
        mock_settings_result, 
        mock_food_totals, 
        mock_water_result, 
        mock_history_desc, 
        mock_used_features,
        mock_fridge_result
    ]
    
    mocker.patch("services.ai_guide.AIGuideService.get_history_context", new_callable=AsyncMock, return_value="")
    mock_ai = mocker.patch("services.ai_guide.AIService.get_completion", new_callable=AsyncMock)
    mock_ai.return_value = "Mocked Food Response"
    
    mocker.patch("services.ai_guide.AIGuideService.save_to_history", new_callable=AsyncMock)
    mocker.patch("services.ai_guide.AIGuideService.check_and_compress", new_callable=AsyncMock)

    current_meal = {"name": "Борщ", "calories": 300, "protein": 15, "fat": 10, "carbs": 25, "time": "14:00"}
    response = await AIGuideService.get_contextual_advice(1, current_meal, session_mock)
    
    assert response == "Mocked Food Response"
    prompt = mock_ai.call_args[0][0]
    
    # Assert that the new 3-preset prompt instructions are injected
    assert "ИНСТРУКЦИЯ ПО ХАРАКТЕРУ (ПРЕСЕТ: direct)" in prompt
    assert "- [hard]: ругай за перебор калорий" in prompt
    assert "- [soft]: хвали за любые успехи" in prompt
    assert "- [direct]: давай сухую аналитику без эмоций" in prompt

