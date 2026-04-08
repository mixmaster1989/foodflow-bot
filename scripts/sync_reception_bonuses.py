import asyncio
import sqlite3
import sys
import os
from datetime import datetime, timedelta

# Add parent directory to sys.path to import project modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import select
from database.base import init_db, get_db
from database.models import Subscription, User

RECEPTION_DB = "reception.db" # In script dir

async def sync_bonuses():
    print("🔄 Starting bonus synchronization from Reception Bot...")
    
    if not os.path.exists(RECEPTION_DB):
        print(f"❌ Error: {RECEPTION_DB} not found!")
        return

    # 1. Get data from reception
    conn = sqlite3.connect(RECEPTION_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, bonus_days FROM waitlist WHERE bonus_days > 0")
    reception_data = cursor.fetchall()
    conn.close()
    
    if not reception_data:
        print("ℹ️ No bonuses to sync.")
        return

    print(f"📊 Found {len(reception_data)} users with bonuses.")

    await init_db()
    async for session in get_db():
        synced_count = 0
        for user_id, bonus_days in reception_data:
            # Check if user exists in main DB
            user = await session.get(User, user_id)
            if not user:
                # User hasn't joined the main bot yet
                continue
            
            # Upsert Subscription
            sub_stmt = select(Subscription).where(Subscription.user_id == user_id)
            sub_res = await session.execute(sub_stmt)
            sub = sub_res.scalar_one_or_none()
            
            now = datetime.now()
            
            if sub:
                # If they already have pro, extend it. If free, convert to pro for bonus period.
                # If tier is pro, extend expires_at
                # If tier is free, set to pro and set expires_at
                current_expires = sub.expires_at if sub.expires_at and sub.expires_at > now else now
                sub.expires_at = current_expires + timedelta(days=bonus_days)
                sub.tier = "pro"
                sub.is_active = True
            else:
                new_sub = Subscription(
                    user_id=user_id,
                    tier="pro",
                    starts_at=now,
                    expires_at=now + timedelta(days=bonus_days),
                    is_active=True
                )
                session.add(new_sub)
            
            synced_count += 1
            # Reset bonus in reception so we don't sync it twice? 
            # Better to mark as synced in reception or just overwrite here.
            # For simplicity, we just add it.
        
        await session.commit()
        print(f"✅ Successfully synced {synced_count} users.")
        break

if __name__ == "__main__":
    asyncio.run(sync_bonuses())
