
import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy import select
from datetime import datetime

from handlers import i_ate
from database.models import User, ConsumptionLog

@pytest.mark.asyncio
async def test_i_ate_flow_integration(db_session):
    """
    Integration test for 'I Ate' flow:
    1. Create user in DB.
    2. Simulate 'Confimation' step.
    3. Simulate 'Save' click.
    4. Verify data in real DB.
    """
    # 1. Setup User
    user_id = 112233
    user = User(id=user_id, username="integration_tester", first_name="Int", last_name="Test")
    db_session.add(user)
    await db_session.commit()

    # 2. Setup Mock Objects
    message = AsyncMock()
    message.edit_text = AsyncMock()
    callback = AsyncMock()
    callback.from_user.id = user_id
    callback.message = message
    
    state = AsyncMock()
    
    # Mock data that would be in FSM after user says "Apple 100g"
    pending_data = {
        "pending_product": {
            "name": "Apple (100г)",
            "base_name": "Apple",
            "calories100": 52.0,
            "protein100": 0.3,
            "fat100": 0.2,
            "carbs100": 13.8,
            "fiber100": 2.4
        }
    }
    state.get_data.return_value = pending_data
    
    # 3. Simulate Clicking "Confirm" (process_confirm)
    # We need to patch get_db to return our test db_session
    async def mock_get_db():
        yield db_session

    with patch('handlers.i_ate.get_db', side_effect=mock_get_db):
        await i_ate.process_confirm(callback, state)
    
    # 4. Verify DB persistence
    # Perform a real SELECT query
    result = await db_session.execute(
        select(ConsumptionLog).where(ConsumptionLog.user_id == user_id)
    )
    logs = result.scalars().all()
    
    assert len(logs) == 1
    log = logs[0]
    assert log.product_name == "Apple (100г)"
    assert log.calories == 52.0
    assert log.carbs == 13.8  # Verify it saved the correct data
    
    # Verify State was cleared
    state.clear.assert_called_once()
    
    # Verify UI feedback
    assert "✅ <b>Сохранено:</b>" in callback.message.edit_text.call_args[0][0]

