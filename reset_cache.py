
import asyncio
from sqlalchemy import select
from database.base import get_db, init_db
from database.models import UserSettings

DATABASE_URL = "sqlite+aiosqlite:///./foodflow.db"

async def reset_cache(user_id):
    await init_db()
    
    print(f"🔄 Resetting cache for {user_id}...")
    async for session in get_db():
        stmt = select(UserSettings).where(UserSettings.user_id == user_id)
        settings = (await session.execute(stmt)).scalar_one_or_none()
        
        if settings:
            settings.fridge_summary_cache = None
            settings.fridge_summary_date = None
            session.add(settings)
            await session.commit()
            print("✅ Cache cleared!")
        else:
            print("❌ User settings not found.")
        return

if __name__ == "__main__":
    asyncio.run(reset_cache(432823154))
