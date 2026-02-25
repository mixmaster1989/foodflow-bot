from datetime import datetime
from unittest.mock import patch

import pytest

from database.models import ConsumptionLog, User
from handlers.curator import curator_ward_detail, curator_ward_logs_list
from tests.conftest import AsyncMock


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
            date=datetime.now()
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

        # Check either edit_media or answer_photo
        if callback.message.edit_media.called:
            args, kwargs = callback.message.edit_media.call_args
            caption = kwargs.get('media').caption if 'media' in kwargs else args[0].caption
        else:
            args, kwargs = callback.message.answer_photo.call_args
            caption = kwargs.get('caption') or args[1]

        assert "📅" in caption

        # Verify "Full list" button
        markup = kwargs['reply_markup']
        found_full_list = False
        for row in markup.inline_keyboard:
            for btn in row:
                if "Весь список" in btn.text:
                    found_full_list = True
                    # Format changed to curator_ward_logs:{ward_id}:{page}:{date}
                    assert btn.callback_data.startswith(f"curator_ward_logs:{ward_id}:0")

        assert found_full_list

        # 4. Test Full Logs List View (Page 0)
        callback_logs = AsyncMock()
        callback_logs.from_user.id = curator_id
        # New format: curator_ward_logs:{ward_id}:{page}:{date}
        today_str = datetime.now().strftime("%Y-%m-%d")
        callback_logs.data = f"curator_ward_logs:{ward_id}:0:{today_str}"
        callback_logs.message = AsyncMock()

        await curator_ward_logs_list(callback_logs)

        args_list, kwargs_list = callback_logs.message.edit_text.call_args
        list_text = args_list[0]
        assert "Еда за" in list_text
        assert "1/2" in list_text
        assert list_text.count("•") == 10

        # Check next page button
        markup_list = kwargs_list['reply_markup']
        assert any("➡️" in btn.text for row in markup_list.inline_keyboard for btn in row)

