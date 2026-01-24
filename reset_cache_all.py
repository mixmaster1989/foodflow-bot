
import asyncio
from sqlalchemy import select, update
from database.base import get_db, init_db
from database.models import UserSettings

async def reset_all_cache():
    await init_db()
    
    print("🔄 Resetting fridge summary cache for ALL users...")
    async for session in get_db():
        stmt = update(UserSettings).values(
            fridge_summary_cache=None,
            fridge_summary_date=None
        )
        result = await session.execute(stmt)
        await session.commit()
        print(f"✅ Cache cleared for {result.rowcount} users!")
        return

if __name__ == "__main__":
    asyncio.run(reset_all_cache())
