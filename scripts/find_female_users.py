import asyncio
from sqlalchemy import select
from database.base import get_db
from database.models import User, UserSettings

async def main():
    print("🔍 Searching for female users...")
    count = 0
    async for session in get_db():
        stmt = (
            select(User.id, User.username, User.first_name, User.last_name)
            .join(UserSettings, User.id == UserSettings.user_id)
            .where(UserSettings.gender == 'female')
        )
        result = await session.execute(stmt)
        users = result.all()
        
        if not users:
            print("No female users found.")
            return

        print(f"\n✨ Found {len(users)} female users:\n")
        print(f"{'ID':<15} | {'Username':<20} | {'Name':<30}")
        print("-" * 70)
        
        for user_id, username, first_name, last_name in users:
            full_name = f"{first_name or ''} {last_name or ''}".strip()
            print(f"{user_id:<15} | {username or 'N/A':<20} | {full_name or 'N/A':<30}")
            count += 1
        break

if __name__ == "__main__":
    asyncio.run(main())
