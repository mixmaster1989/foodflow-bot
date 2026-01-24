#!/usr/bin/env python3
"""Reset user for fresh onboarding test."""
import asyncio
import sys
sys.path.insert(0, '/home/user1/foodflow-bot')

from sqlalchemy import update
from database.base import engine

async def reset_user_for_onboarding(user_id: int):
    """Reset is_verified and delete UserSettings for user."""
    async with engine.begin() as conn:
        # Reset is_verified
        await conn.execute(
            update(
                __import__('database.models', fromlist=['User']).User
            ).where(
                __import__('database.models', fromlist=['User']).User.id == user_id
            ).values(is_verified=False)
        )
        
        # Delete UserSettings
        from database.models import UserSettings
        from sqlalchemy import delete
        await conn.execute(
            delete(UserSettings).where(UserSettings.user_id == user_id)
        )
        
        print(f"✅ User {user_id} reset for fresh onboarding")

if __name__ == '__main__':
    user_id = 8560434937  # Елена
    asyncio.run(reset_user_for_onboarding(user_id))
