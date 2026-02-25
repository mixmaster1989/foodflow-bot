import pytest
import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session
from database.models import User, Marathon, MarathonParticipant, UserSettings
from handlers.common import cmd_start
from services.marathon_service import MarathonService
from aiogram.types import Message, Chat, User as TgUser

# Mock data
MOCK_CURATOR_ID = 555
MOCK_MARATHON_ID = 101
MOCK_NEW_USER_ID = 777
MOCK_EXISTING_USER_ID = 888
MOCK_BUSY_USER_ID = 999

@pytest.mark.asyncio
async def test_marathon_invite_new_user(db_session: Session):
    """Test A: New user joins via link -> Created, VERIFIED, Participant, NO curator_id."""
    # 1. Setup Marathon
    curator = User(id=MOCK_CURATOR_ID, username="admin", is_verified=True, role="curator")
    db_session.add(curator)
    marathon = Marathon(
        id=MOCK_MARATHON_ID,
        curator_id=MOCK_CURATOR_ID,
        name="Test Run",
        start_date=datetime.datetime.now(),
        end_date=datetime.datetime.now() + datetime.timedelta(days=7),
        is_active=True,
        is_registration_open=True 
    )
    db_session.add(marathon)
    await db_session.commit()

    # 2. Simulate /start m_101
    message = Message(
        message_id=1,
        date=datetime.datetime.now(),
        chat=Chat(id=MOCK_NEW_USER_ID, type="private"),
        from_user=TgUser(id=MOCK_NEW_USER_ID, is_bot=False, first_name="New", username="newbie"),
        text=f"/start m_{MOCK_MARATHON_ID}"
    )
    
    # Needs a mock state, but for integration logic we might call helper or use full stack.
    # For now, let's assume we call a logic function we WILL refactor out, 
    # OR we mock the handler call. 
    # Since cmd_start is complex with FSM, verifying DB state is key.
    
    # ... Wait, we haven't implemented logic yet. This test is TDD.
    # We will invoke the HANDLER (when implemented) or simulate the logic block.
    # Since we can't run handler without dispatcher context easily here without mocks, 
    # let's plan the test expectation.
    # 3. Call Service
    user_info = {"username": "newbie", "first_name": "New", "last_name": "User"}
    result = await MarathonService.process_invite(
        db_session, 
        MOCK_MARATHON_ID, 
        MOCK_NEW_USER_ID, 
        user_info
    )
    
    # 4. Verify Result
    assert result["success"] is True
    assert result["is_new_user"] is True
    
    # 5. Verify DB State
    user = await db_session.get(User, MOCK_NEW_USER_ID)
    assert user is not None
    assert user.is_verified is True
    assert user.curator_id is None # Should NOT be linked as ward
    
    # Verify Participation
    stmt = select(MarathonParticipant).where(
        MarathonParticipant.user_id == MOCK_NEW_USER_ID,
        MarathonParticipant.marathon_id == MOCK_MARATHON_ID
    )
    part = (await db_session.execute(stmt)).scalar_one_or_none()
    assert part is not None
    assert part.is_active is True

@pytest.mark.asyncio
async def test_marathon_invite_closed_registration(db_session: Session):
    """Test D: User tries to join closed marathon -> Fail."""
    # Setup Closed Marathon
    curator = User(id=MOCK_CURATOR_ID + 1, username="admin2", role="curator")
    db_session.add(curator)
    marathon = Marathon(
        curator_id=curator.id,
        name="Closed Run",
        start_date=datetime.datetime.now(),
        end_date=datetime.datetime.now(),
        is_active=True,
        is_registration_open=False # CLOSED
    )
    db_session.add(marathon)
    await db_session.commit()
    
    # Call Service
    user_info = {"username": "latedude", "first_name": "Late", "last_name": "Dude"}
    result = await MarathonService.process_invite(
        db_session, 
        marathon.id, 
        MOCK_NEW_USER_ID + 1, 
        user_info
    )
    
    # Expect Failure
    assert result["success"] is False
    assert "закрыта" in result["message"]
    
    # Verify NOT in DB
    stmt = select(MarathonParticipant).where(
        MarathonParticipant.user_id == MOCK_NEW_USER_ID + 1
    )
    part = (await db_session.execute(stmt)).scalar_one_or_none()
    assert part is None
