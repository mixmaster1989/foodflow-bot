import pytest
from datetime import datetime
from unittest.mock import patch
from database.models import User, ConsumptionLog
from handlers.curator import curator_ward_detail, curator_ward_logs_list
from tests.conftest import AsyncMock, MagicMock

@pytest.mark.asyncio
async def test_curator_full_logs_view(db_session):
    # 1. Setup Curator and Ward in test DB
    curator_id = 12345
    ward_id = 67890
    
    curator = User(id=curator_id, username="curator_boss")
    ward = User(id=ward_id, username="ward_student", curator_id=curator_id)
    
    db_session.add(curator)
    db_session.add(ward)
    await db_session.commit()
    
    # 2. Add 15 logs for Ward today
    for i in range(15):
        log = ConsumptionLog(
            user_id=ward_id,
            product_name=f"Ingredient {i+1}",
            base_name=f"ingredient_{i+1}",
            calories=100,
            protein=10,
            fat=5,
            carbs=20,
            date=datetime.utcnow()
        )
        db_session.add(log)
    await db_session.commit()
    
    # 3. Patch get_db to return our test session
    async def mock_get_db():
        yield db_session

    with patch('handlers.curator.get_db', side_effect=mock_get_db):
        # Test Detail View
        callback = AsyncMock()
        callback.from_user.id = curator_id
        callback.data = f"curator_ward:{ward_id}"
        callback.message = AsyncMock()
        
        await curator_ward_detail(callback)
        
        args, kwargs = callback.message.edit_text.call_args
        text = args[0]
        assert "Последние приёмы" in text
        
        # Verify "Full list" button
        markup = kwargs['reply_markup']
        found_full_list = False
        for row in markup.inline_keyboard:
            for btn in row:
                if "Весь список" in btn.text:
                    found_full_list = True
                    assert btn.callback_data == f"curator_ward_logs:{ward_id}:0"
        
        assert found_full_list

        # 4. Test Full Logs List View (Page 0)
        callback_logs = AsyncMock()
        callback_logs.from_user.id = curator_id
        callback_logs.data = f"curator_ward_logs:{ward_id}:0"
        callback_logs.message = AsyncMock()
        
        await curator_ward_logs_list(callback_logs)
        
        args_list, kwargs_list = callback_logs.message.edit_text.call_args
        list_text = args_list[0]
        assert "Еда за сегодня" in list_text
        assert "1/2" in list_text
        assert list_text.count("•") == 10
        
        # Check next page button
        markup_list = kwargs_list['reply_markup']
        assert any("Следующая" in btn.text for row in markup_list.inline_keyboard for btn in row)

