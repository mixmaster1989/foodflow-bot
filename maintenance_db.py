
import asyncio
import aiosqlite
from config import settings

async def maintenance():
    print("--- DB MAINTENANCE START ---")
    print("--- DB MAINTENANCE START ---")
    # Extract path from DATABASE_URL or build it manually
    # settings.DATABASE_URL is "sqlite+aiosqlite:////home/user1/foodflow-bot/foodflow.db"
    if "sqlite" in settings.DATABASE_URL:
        db_path = settings.DATABASE_URL.split("///")[-1]
    else:
        db_path = str(settings.BASE_DIR / "foodflow.db")
        
    print(f"Target DB: {db_path}")
    
    async with aiosqlite.connect(db_path) as db:
        print("1. Forcing WAL Checkpoint (TRUNCATE)...")
        await db.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        await db.commit()
        
        print("2. Optimizing (VACUUM)...")
        await db.execute("VACUUM;")
        await db.commit()
        
    print("--- DB MAINTENANCE COMPLETE ---")

if __name__ == "__main__":
    asyncio.run(maintenance())
