"""Simple smoke test for Marathon module."""

import asyncio
import sys
import os
from datetime import datetime, timedelta

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, delete
from database.base import async_session, init_db
from database.models import (
    User, Marathon, MarathonParticipant, SnowflakeLog
)

TEST_MARATHON_NAME = "AUTO_TEST_MARATHON_12345"


async def run_smoke_test():
    """Run a simple smoke test for Marathon module."""
    print("=" * 50)
    print("🏃 MARATHON MODULE SMOKE TEST")
    print("=" * 50)
    
    await init_db()
    
    async with async_session() as session:
        # 1. Clean up any previous test data
        print("\n🧹 Cleaning up old test data...")
        await session.execute(
            delete(Marathon).where(Marathon.name == TEST_MARATHON_NAME)
        )
        await session.commit()
        print("   ✅ Cleaned")
        
        # 2. Create Marathon
        print("\n🧪 TEST 1: Create Marathon...")
        marathon = Marathon(
            curator_id=432823154,
            name=TEST_MARATHON_NAME,
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=30),
            is_active=True,
            waves_config={}
        )
        session.add(marathon)
        await session.commit()
        await session.refresh(marathon)
        
        assert marathon.id is not None
        print(f"   ✅ Marathon created ID={marathon.id}")
        
        # 3. Get a test user
        print("\n🧪 TEST 2: Add Participant...")
        user = await session.scalar(select(User).limit(1))
        
        if not user:
            print("   ⚠️ No users in DB. Creating test user...")
            user = User(id=999999999, username="test_auto_user")
            session.add(user)
            await session.commit()
        
        participant = MarathonParticipant(
            marathon_id=marathon.id,
            user_id=user.id,
            start_weight=75.0,
            total_snowflakes=0,
            is_active=True
        )
        session.add(participant)
        await session.commit()
        await session.refresh(participant)
        
        assert participant.id is not None
        print(f"   ✅ Participant added ID={participant.id}")
        
        # 4. Add snowflakes
        print("\n🧪 TEST 3: Add Snowflakes...")
        participant.total_snowflakes += 10
        
        log = SnowflakeLog(
            participant_id=participant.id,
            curator_id=432823154,
            amount=10,
            reason="Test"
        )
        session.add(log)
        await session.commit()
        await session.refresh(participant)
        
        assert participant.total_snowflakes == 10
        print(f"   ✅ Snowflakes: {participant.total_snowflakes}")
        
        # 5. Stop Marathon
        print("\n🧪 TEST 4: Stop Marathon...")
        marathon.is_active = False
        await session.commit()
        await session.refresh(marathon)
        
        assert marathon.is_active == False
        print("   ✅ Marathon stopped")
        
        # 6. Cleanup
        print("\n🧹 Final cleanup...")
        await session.execute(
            delete(SnowflakeLog).where(SnowflakeLog.participant_id == participant.id)
        )
        await session.execute(
            delete(MarathonParticipant).where(MarathonParticipant.marathon_id == marathon.id)
        )
        await session.execute(
            delete(Marathon).where(Marathon.id == marathon.id)
        )
        await session.commit()
        print("   ✅ Cleaned")
    
    print("\n" + "=" * 50)
    print("✅ ALL SMOKE TESTS PASSED!")
    print("=" * 50)
    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(run_smoke_test())
        sys.exit(exit_code)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
