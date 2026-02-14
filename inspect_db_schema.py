
import asyncio
from sqlalchemy import text
from database.base import get_db

async def inspect():
    print("--- DB INSPECTION START ---")
    async for session in get_db():
        # Get all tables
        res = await session.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        tables = [row[0] for row in res.fetchall()]
        
        for table in tables:
            print(f"TABLE: {table}")
            # Get columns for each table
            cols = await session.execute(text(f"PRAGMA table_info({table})"))
            for col in cols.fetchall():
                # col format: (cid, name, type, notnull, dflt_value, pk)
                print(f"  - {col[1]} ({col[2]})")
        break
    print("--- DB INSPECTION END ---")

if __name__ == "__main__":
    asyncio.run(inspect())
