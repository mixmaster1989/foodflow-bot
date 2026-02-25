
import asyncio
import os
import sys

from sqlalchemy import select

# Add current dir to sys.path to mimic bot behavior
sys.path.append(os.getcwd())

try:
    from config import settings
    # Try to find DB path variable (it might be in .env or settings attributes)
    print(f"DEBUG: settings dir: {dir(settings)}")

    # Assuming standard attr names
    db_url = getattr(settings, 'DB_URL', 'Not Found')
    db_path = getattr(settings, 'DB_PATH', 'Not Found')
    sqlite_path = getattr(settings, 'sqlite_db_path', 'Not Found')

    print(f"DEBUG: DB_URL={db_url}")
    print(f"DEBUG: DB_PATH={db_path}")
    print(f"DEBUG: sqlite_db_path={sqlite_path}")

    print(f"DEBUG: CWD={os.getcwd()}")
    print(f"DEBUG: List Dir: {os.listdir('.')}")

    from sqlalchemy import text  # Added import

    from database.base import get_db
    from database.models import User

    async def check():
        print("--- QUERY START ---")
        async for session in get_db():
            # Check for user 432823154
            stmt = select(User).where(User.id == 432823154)
            user = (await session.execute(stmt)).scalar_one_or_none()
            if user:
                print(f"✅ USER FOUND: {user.id} Verified={user.is_verified}")
            else:
                print("❌ USER 432823154 NOT FOUND")

            # Count users
            res = await session.execute(text("SELECT count(*) FROM users")) # Wrapped in text()
            print(f"COUNT: {res.scalar()}")
            break
        print("--- QUERY END ---")

    if __name__ == "__main__":
        asyncio.run(check())

except Exception:
    import traceback
    traceback.print_exc()
