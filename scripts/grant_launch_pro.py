import asyncio
import sys
import os
from datetime import datetime, timedelta

# Add parent directory to sys.path to import project modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import select
from database.base import init_db, get_db
from database.models import User, Subscription

async def grant_pro_to_all():
    print("🚀 Starting mass PRO granting campaign...")
    await init_db()
    
    async for session in get_db():
        # 1. Get all users
        stmt = select(User)
        result = await session.execute(stmt)
        users = result.scalars().all()
        
        counts = {"updated": 0, "created": 0}
        now = datetime.now()
        expires_at = now + timedelta(days=30)
        
        for user in users:
            # Grant Founding Member status
            user.is_founding_member = True
            user.is_premium = True
            
            # Upsert Subscription
            sub_stmt = select(Subscription).where(Subscription.user_id == user.id)
            sub_res = await session.execute(sub_stmt)
            sub = sub_res.scalar_one_or_none()
            
            if sub:
                sub.tier = "pro"
                sub.starts_at = now
                sub.expires_at = expires_at
                sub.is_active = True
                counts["updated"] += 1
            else:
                new_sub = Subscription(
                    user_id=user.id,
                    tier="pro",
                    starts_at=now,
                    expires_at=expires_at,
                    is_active=True
                )
                session.add(new_sub)
                counts["created"] += 1
        
        await session.commit()
        print(f"📊 Campaign finished!")
        print(f"✅ Total users processed: {len(users)}")
        print(f"✨ Subscriptions updated: {counts['updated']}")
        print(f"🆕 Subscriptions created: {counts['created']}")
        break # Exit after one session

if __name__ == "__main__":
    asyncio.run(grant_pro_to_all())
