import asyncio
from sqlalchemy import select
from database.base import init_db, get_db
from database.models import Subscription

async def main():
    user_id = 432823154
    await init_db()
    async for session in get_db():
        stmt = select(Subscription).where(Subscription.user_id == user_id)
        sub = (await session.execute(stmt)).scalar_one_or_none()
        
        if sub:
            sub.tier = "free"
            sub.is_active = True
            sub.expires_at = None
            sub.telegram_payment_charge_id = None
            sub.payment_source = None
            sub.yookassa_payment_id = None
            print(f"Downgraded subscription for user {user_id} to FREE.")
        else:
            sub = Subscription(user_id=user_id, tier="free", is_active=True)
            session.add(sub)
            print(f"Created new FREE subscription for user {user_id}.")
            
        await session.commit()
        break

if __name__ == "__main__":
    asyncio.run(main())
