import asyncio
import sys
from pathlib import Path

# Add root directory to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from database.base import init_db, get_db
from database.models import User, UserSettings
from sqlalchemy.future import select

async def check_user(user_id):
    await init_db()
    async for session in get_db():
        # Check User table
        stmt = select(User).where(User.id == user_id)
        user = (await session.execute(stmt)).scalar_one_or_none()
        print(f"User {user_id}: {user}")
        if user:
            print(f"  is_verified: {user.is_verified}")
            print(f"  created_at: {user.created_at}")
        
        # Check UserSettings
        stmt = select(UserSettings).where(UserSettings.user_id == user_id)
        settings = (await session.execute(stmt)).scalar_one_or_none()
        print(f"Settings for {user_id}: {settings}")
        if settings:
            print(f"  is_initialized: {settings.is_initialized}")
        else:
            print("  No settings found!")

if __name__ == "__main__":
    asyncio.run(check_user(432823154))
