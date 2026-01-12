import asyncio
from sqlalchemy import text
from database.base import async_session

async def migrate():
    async with async_session() as session:
        print("Starting Fiber Migration...")
        
        # 1. Products
        try:
            await session.execute(text("ALTER TABLE products ADD COLUMN fiber FLOAT DEFAULT 0.0"))
            print("✅ Added 'fiber' to products")
        except Exception as e:
            print(f"⚠️ Products skip: {e}")

        # 2. Consumption Logs
        try:
            await session.execute(text("ALTER TABLE consumption_logs ADD COLUMN fiber FLOAT DEFAULT 0.0"))
            print("✅ Added 'fiber' to consumption_logs")
        except Exception as e:
            print(f"⚠️ Logs skip: {e}")

        # 3. Label Scans
        try:
            await session.execute(text("ALTER TABLE label_scans ADD COLUMN fiber FLOAT DEFAULT 0.0"))
            print("✅ Added 'fiber' to label_scans")
        except Exception as e:
            print(f"⚠️ LabelScans skip: {e}")

        # 4. User Settings (Goal)
        try:
            await session.execute(text("ALTER TABLE user_settings ADD COLUMN fiber_goal INTEGER DEFAULT 30"))
            print("✅ Added 'fiber_goal' to user_settings")
        except Exception as e:
            print(f"⚠️ Settings skip: {e}")

        await session.commit()
        print("Migration complete.")

if __name__ == "__main__":
    asyncio.run(migrate())
