import asyncio
import sys
from datetime import datetime
from sqlalchemy import select, func, and_
from database.base import get_db
from database.models import User, UserSettings, WaterLog

# Ensure importing from bot root works
sys.path.append('.')

async def main():
    print("💧 Starting Water Tracking Test...")
    
    # 1. Setup Test User
    test_user_id = 123456789
    
    async for session in get_db():
        # Clean up existing data for test user
        stmt_del_water = select(WaterLog).where(WaterLog.user_id == test_user_id)
        for w in (await session.execute(stmt_del_water)).scalars():
            await session.delete(w)
            
        stmt_del_settings = select(UserSettings).where(UserSettings.user_id == test_user_id)
        for s in (await session.execute(stmt_del_settings)).scalars():
            await session.delete(s)
            
        stmt_del_user = select(User).where(User.id == test_user_id)
        u = (await session.execute(stmt_del_user)).scalar_one_or_none()
        if u:
            await session.delete(u)
            
        await session.commit()
        
        # Create Test User
        user = User(id=test_user_id, username="water_tester", first_name="Water", last_name="Tester", role="user")
        session.add(user)
        
        # Test default water goal is 2000
        settings = UserSettings(user_id=test_user_id, weight=70, goal="healthy")
        session.add(settings)
        await session.commit()
        
        print(f"✅ User {test_user_id} created with default water_goal: {settings.water_goal}ml")

    # 2. Add Water Intake
    print("\n💧 Simulating water intake...")
    async for session in get_db():
        log1 = WaterLog(user_id=test_user_id, amount_ml=250)
        log2 = WaterLog(user_id=test_user_id, amount_ml=500)
        session.add_all([log1, log2])
        await session.commit()
        print("✅ Added 250ml and 500ml.")

    # 3. Verify Aggregation (as used in handlers/menu.py)
    print("\n📊 Checking aggregation logic...")
    async for session in get_db():
        today = datetime.utcnow().date()
        water_stmt = select(func.sum(WaterLog.amount_ml)).where(
            and_(
                WaterLog.user_id == test_user_id,
                func.date(WaterLog.date) == today
            )
        )
        water_total = (await session.execute(water_stmt)).scalar() or 0
        print(f"Sum result: {water_total}ml")
        assert water_total == 750, f"Expected 750, got {water_total}"
        print("✅ Aggregation gives correct total.")
        
    # 4. Cleanup
    async for session in get_db():
        stmt = select(WaterLog).where(WaterLog.user_id == test_user_id)
        for w in (await session.execute(stmt)).scalars():
            await session.delete(w)
        stmt2 = select(UserSettings).where(UserSettings.user_id == test_user_id)
        s = (await session.execute(stmt2)).scalar_one_or_none()
        await session.delete(s)
        stmt3 = select(User).where(User.id == test_user_id)
        u = (await session.execute(stmt3)).scalar_one_or_none()
        await session.delete(u)
        await session.commit()
    print("\n✨ Test completed successfully!")

if __name__ == "__main__":
    asyncio.run(main())
