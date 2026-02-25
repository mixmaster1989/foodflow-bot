
import asyncio
import logging
from sqlalchemy import select
from database.base import get_db
from database.models import User

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_user(user_id):
    logger.info(f"Checking user {user_id}...")
    try:
        async for session in get_db():
            stmt = select(User).where(User.id == user_id)
            user = (await session.execute(stmt)).scalar_one_or_none()
            if user:
                logger.info(f"SUCCESS: Found user {user.id}, Verified={user.is_verified}")
            else:
                logger.error(f"FAILURE: User {user_id} NOT FOUND")
            return
    except Exception as e:
        logger.error(f"EXCEPTION: {e}")

if __name__ == "__main__":
    # Use the ID from the log grep earlier (Update id=958091369 -> user?) 
    # Or use the user_id mentioned in the "Sent weight reminder" log: 295543071
    asyncio.run(check_user(295543071))
