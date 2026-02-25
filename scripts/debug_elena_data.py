import asyncio
import logging
import sys
from pathlib import Path

# Add root directory to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from sqlalchemy.future import select
from database.base import init_db, get_db
from database.models import User, Product, ConsumptionLog, Receipt

logging.basicConfig(level=logging.INFO)

TARGET_USER_ID = 911990304

async def check_user_data():
    await init_db()
    async for session in get_db():
        # Check User Info
        u_stmt = select(User).where(User.id == TARGET_USER_ID)
        user = (await session.execute(u_stmt)).scalar_one_or_none()
        
        if not user:
            print("User not found.")
            return

        print(f"User: {user.username} (ID: {user.id})")
        print(f"Created: {user.created_at}")
        print(f"Verified: {user.is_verified}")

        # Check Products
        p_stmt = select(Product).where(Product.user_id == TARGET_USER_ID)
        products = (await session.execute(p_stmt)).scalars().all()
        print(f"Products Logged: {len(products)}")
        for p in products[:5]:
            print(f" - {p.name} ({p.source})")

        # Check Consumption
        c_stmt = select(ConsumptionLog).where(ConsumptionLog.user_id == TARGET_USER_ID)
        logs = (await session.execute(c_stmt)).scalars().all()
        print(f"Consumption Logs: {len(logs)}")
        for l in logs[:5]:
             print(f" - {l.product_name} ({l.date})")
             
        # Check Receipts
        r_stmt = select(Receipt).where(Receipt.user_id == TARGET_USER_ID)
        receipts = (await session.execute(r_stmt)).scalars().all()
        print(f"Receipts: {len(receipts)}")

if __name__ == "__main__":
    asyncio.run(check_user_data())
