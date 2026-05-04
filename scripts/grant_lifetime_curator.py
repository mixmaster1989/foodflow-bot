import asyncio
import sys
import os

# Add parent directory to sys.path to import project modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import select
from database.base import init_db, get_db
from database.models import PAYMENT_SOURCE_ADMIN, Subscription, User

CORE_TEAM_IDS = [432823154, 295543071, 33587682]

async def grant_lifetime_curator():
    print(f"🎖 Granting Lifetime Curator status to core team {CORE_TEAM_IDS}...")
    await init_db()
    
    async for session in get_db():
        for uid in CORE_TEAM_IDS:
            # 1. Ensure User is premium
            user_stmt = select(User).where(User.id == uid)
            user_res = await session.execute(user_stmt)
            user = user_res.scalar_one_or_none()
            
            if user:
                user.is_premium = True
                user.role = "curator" # Also set role to curator
                
                # 2. Update/Create Subscription
                sub_stmt = select(Subscription).where(Subscription.user_id == uid)
                sub_res = await session.execute(sub_stmt)
                sub = sub_res.scalar_one_or_none()
                
                if sub:
                    sub.tier = "curator"
                    sub.expires_at = None # Lifetime
                    sub.is_active = True
                    sub.payment_source = PAYMENT_SOURCE_ADMIN
                    print(f"✅ Updated existing subscription for {uid} to Lifetime Curator")
                else:
                    new_sub = Subscription(
                        user_id=uid,
                        tier="curator",
                        starts_at=datetime.now(),
                        expires_at=None,
                        is_active=True,
                        payment_source=PAYMENT_SOURCE_ADMIN,
                    )
                    session.add(new_sub)
                    print(f"✅ Created new Lifetime Curator subscription for {uid}")
            else:
                print(f"⚠️ User {uid} not found in database!")
                
        await session.commit()
        print("✨ Lifetime Curator grant complete!")
        break

if __name__ == "__main__":
    asyncio.run(grant_lifetime_curator())
