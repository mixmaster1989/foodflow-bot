import asyncio
import logging
import sys
from pathlib import Path

# Add root directory to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from sqlalchemy.future import select
from database.base import init_db, get_db
from database.models import User

logging.basicConfig(level=logging.INFO)

async def check_status():
    await init_db()
    async for session in get_db():
        stmt = select(User).where(User.id == 7846721167)
        user = (await session.execute(stmt)).scalar_one_or_none()
        
        if user:
            print(f"User Found: {user.username}")
            print(f"Verified: {user.is_verified}")
        else:
            print("User NOT found in DB")

if __name__ == "__main__":
    asyncio.run(check_status())
