import asyncio

from sqlalchemy import text

from database.base import Base, engine


async def reset_analytics_table():
    print("Resetting product_events table...")
    async with engine.begin() as conn:
        # Drop if exists
        await conn.execute(text("DROP TABLE IF EXISTS product_events"))
        # Recreate all (it will only create missing ones, and since we dropped it, it will recreate product_events)
        await conn.run_sync(Base.metadata.create_all)
    print("Table product_events recreated successfully.")

if __name__ == "__main__":
    asyncio.run(reset_analytics_table())
