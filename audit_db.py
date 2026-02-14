
import asyncio
from sqlalchemy import select, text
from database.base import get_db
from database.models import User

async def analyze_db():
    print("--- DB ANALYSIS START ---")
    async for session in get_db():
        # 1. Count Users
        result = await session.execute(text("SELECT COUNT(*) FROM users"))
        count = result.scalar()
        print(f"Total Users: {count}")
        
        # 2. List all IDs (limit 10)
        stmt = select(User.id, User.username, User.is_verified).limit(10)
        users = (await session.execute(stmt)).all()
        for u in users:
            print(f"User: {u.id} | {u.username} | Verified={u.is_verified}")
            
        # 3. Check specific ID
        target_id = 432823154
        stmt = select(User).where(User.id == target_id)
        user = (await session.execute(stmt)).scalar_one_or_none()
        if user:
            print(f"TARGET {target_id} FOUND! Verified={user.is_verified}")
        else:
            print(f"TARGET {target_id} NOT FOUND.")
        break
    print("--- DB ANALYSIS END ---")

if __name__ == "__main__":
    asyncio.run(analyze_db())
