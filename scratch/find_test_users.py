import asyncio

from sqlalchemy import select

from database.base import get_db
from database.models import User


async def find_test_users():
    async for session in get_db():
        stmt = select(User)
        result = await session.execute(stmt)
        users = result.scalars().all()
        found = False
        for user in users:
            uid_str = str(user.id)
            if user.id < 1000000 or uid_str.startswith('777'):
                print(f"ID: {user.id}, Created At: {user.created_at}")
                found = True
        if not found:
            print("No test users found in top results.")
        break

if __name__ == "__main__":
    asyncio.run(find_test_users())
