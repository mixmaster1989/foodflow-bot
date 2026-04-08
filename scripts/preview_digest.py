
import asyncio
from services.reports import generate_admin_daily_digest
from database.base import get_db

async def preview_digest():
    text = await generate_admin_daily_digest()
    print("-" * 30)
    print(text)
    print("-" * 30)

if __name__ == "__main__":
    asyncio.run(preview_digest())
