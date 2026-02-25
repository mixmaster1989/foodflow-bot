import asyncio
import os
import sys

sys.path.insert(0, os.getcwd())

from sqlalchemy import select

from database.base import async_session
from database.models import UserSettings


async def check_settings():
    # await init_db() # Not needed just to read, engine created on import
    print("Checking settings for user 432823154 via SQLAlchemy...")
    async with async_session() as session:
        stmt = select(UserSettings).where(UserSettings.user_id == 432823154)
        settings = (await session.execute(stmt)).scalar_one_or_none()

        if settings:
            print(f"✅ FOUND! ID={settings.id}, Goal={settings.goal}")
        else:
            print("❌ NOT FOUND via SQLAlchemy")

if __name__ == "__main__":
    asyncio.run(check_settings())
