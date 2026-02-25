import asyncio
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from sqlalchemy import select

from database.base import get_db
from database.models import User


async def main():
    async for session in get_db():
        stmt = select(User).where(User.username.ilike('%zumbaola%'))
        result = await session.execute(stmt)
        users = result.scalars().all()

        print(f"Found {len(users)} users matching 'zumbaola':")
        for u in users:
            name = f"{u.first_name} {u.last_name or ''}".strip()
            print(f"ID: {u.id}, Name: {name}, Username: @{u.username}")

if __name__ == "__main__":
    asyncio.run(main())
