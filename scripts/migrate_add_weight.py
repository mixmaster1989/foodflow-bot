import asyncio
import logging
from sqlalchemy import text
from database.base import async_session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def migrate():
    async with async_session() as session:
        try:
            logger.info("Adding weight_g column to products table...")
            await session.execute(text("ALTER TABLE products ADD COLUMN weight_g FLOAT"))
            await session.commit()
            logger.info("Migration successful!")
        except Exception as e:
            logger.error(f"Migration failed (maybe column exists?): {e}")

if __name__ == "__main__":
    asyncio.run(migrate())
