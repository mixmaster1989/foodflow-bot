
import asyncio
from sqlalchemy import text
from database.base import get_db

async def find_user():
    async for session in get_db():
        res = await session.execute(text("SELECT id, username, first_name, last_name, role FROM users WHERE first_name LIKE '%Ольга%' OR last_name LIKE '%Антакова%'"))
        users = res.fetchall()
        for user in users:
            print(f"ID: {user[0]}, Username: {user[1]}, First: {user[2]}, Last: {user[3]}, Role: {user[4]}")
        break

if __name__ == "__main__":
    asyncio.run(find_user())
