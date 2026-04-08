import asyncio
from datetime import datetime
from sqlalchemy import select
from database.base import get_db
from database.models import Subscription

async def test_sub_query(user_id: int):
    async for session in get_db():
        stmt = select(Subscription).where(Subscription.user_id == user_id)
        sub = (await session.execute(stmt)).scalar_one_or_none()
        
        if not sub:
            print(f"[{user_id}] No subscription found. Status: 🆓 FREE")
            return
            
        tier_icons = {"pro": "💎 PRO", "basic": "🌟 BASIC", "curator": "👑 CURATOR"}
        tier_display = tier_icons.get(sub.tier, "🆓 FREE")
        
        if not sub.is_active:
             print(f"[{user_id}] {tier_display} (Неактивна)")
             return
             
        if not sub.expires_at:
             print(f"[{user_id}] {tier_display} | Бессрочно ∞")
             return
             
        now = datetime.now()
        if sub.expires_at < now:
             print(f"[{user_id}] {tier_display} (Истекла)")
             return
             
        diff = sub.expires_at - now
        if diff.days > 0:
            print(f"[{user_id}] {tier_display} | Осталось: {diff.days} дн.")
        else:
            hours = diff.seconds // 3600
            print(f"[{user_id}] {tier_display} | Осталось: {hours} ч.")
            
        return

async def run_tests():
    # Test on known IDs
    # Pioneer (3 days)
    await test_sub_query(1281838652) 
    # Expired / Old test
    await test_sub_query(142190129) 
    # My Admin / No expiry
    await test_sub_query(295543071)
    
if __name__ == "__main__":
    asyncio.run(run_tests())
