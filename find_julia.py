
import asyncio
from sqlalchemy import text, select
from database.base import get_db

async def find_julia():
    async for session in get_db():
        res = await session.execute(text("SELECT id, first_name, last_name, curator_id FROM users WHERE first_name LIKE '%Юлия%' OR last_name LIKE '%Герасимова%'"))
        users = res.fetchall()
        for u in users:
            print(f"ID: {u[0]}, Name: {u[1]} {u[2]}, CuratorID: {u[3]}")
        break

if __name__ == "__main__":
    asyncio.run(find_julia())
