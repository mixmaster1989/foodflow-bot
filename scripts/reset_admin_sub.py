
import asyncio
from sqlalchemy import select, update
from database.base import init_db, get_db
from database.models import Subscription

async def reset_admin_sub():
    await init_db()
    admin_id = 432823154
    
    async for session in get_db():
        stmt = select(Subscription).where(Subscription.user_id == admin_id)
        sub = (await session.execute(stmt)).scalar_one_or_none()
        
        if sub:
            sub.tier = "free"
            sub.is_active = False
            sub.auto_renew = False
            sub.telegram_payment_charge_id = None
            await session.commit()
            print(f"Successfully reset subscription for user {admin_id} to FREE")
        else:
            print(f"No subscription found for user {admin_id}")
        break

if __name__ == "__main__":
    asyncio.run(reset_admin_sub())
