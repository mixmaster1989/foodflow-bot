import asyncio
from sqlalchemy import select
from database.base import init_db, get_db
from database.models import User

async def main():
    await init_db()
    async for session in get_db():
        stmt = select(User).where(User.role == 'admin')
        result = await session.execute(stmt)
        admins = result.scalars().all()
        for admin in admins:
            print(f"ID: {admin.id} | Username: {admin.username} | Name: {admin.first_name} {admin.last_name} | Role: {admin.role}")
        break

if __name__ == "__main__":
    asyncio.run(main())
