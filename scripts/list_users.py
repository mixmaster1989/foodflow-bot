import asyncio
from sqlalchemy import select
from database.base import init_db, get_db
from database.models import User

async def main():
    await init_db()
    async for session in get_db():
        stmt = select(User)
        result = await session.execute(stmt)
        users = result.scalars().all()
        for u in users:
            print(f"ID: {u.id} | Username: {u.username} | Name: {u.first_name} {u.last_name} | Role: {u.role}")
        break

if __name__ == "__main__":
    asyncio.run(main())
