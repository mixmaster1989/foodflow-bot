import asyncio
import logging
import sys
from pathlib import Path

# Add root directory to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from sqlalchemy.future import select
from database.base import init_db, get_db
from database.models import User

async def list_unverified():
    await init_db()
    async for session in get_db():
        stmt = select(User).where(User.is_verified == False)
        result = await session.execute(stmt)
        users = result.scalars().all()
        
        print(f"Found {len(users)} unverified users:")
        for user in users:
            print(f"ID: {user.id}, Username: {user.username}, Created: {user.created_at}")

if __name__ == "__main__":
    asyncio.run(list_unverified())
