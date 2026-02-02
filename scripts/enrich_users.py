"""
One-time script to enrich existing users with Telegram profile data.

Run this once to update all existing users in the database.
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiogram import Bot
from sqlalchemy import select
from config import settings
from database.base import async_session, init_db
from database.models import User


async def enrich_all_users():
    """Fetch and update profile data for all existing users."""
    await init_db()
    
    bot = Bot(token=settings.BOT_TOKEN)
    
    async with async_session() as session:
        users = (await session.execute(select(User))).scalars().all()
        
        print(f"Found {len(users)} users to enrich")
        print("=" * 50)
        
        enriched = 0
        failed = 0
        
        for db_user in users:
            try:
                # Get fresh data from Telegram
                chat = await bot.get_chat(db_user.id)
                
                # Update fields
                db_user.username = chat.username
                db_user.first_name = chat.first_name
                db_user.last_name = chat.last_name
                
                # Extract bio if available (for user chats)
                if hasattr(chat, 'bio'):
                    pass  # We don't store bio currently
                
                print(f"✅ {db_user.id}: {chat.first_name} {chat.last_name or ''} (@{chat.username or 'no username'})")
                enriched += 1
                
            except Exception as e:
                print(f"❌ {db_user.id}: {e}")
                failed += 1
        
        await session.commit()
        
        print("=" * 50)
        print(f"Enriched: {enriched}/{len(users)}")
        print(f"Failed: {failed}")
    
    await bot.session.close()


if __name__ == "__main__":
    asyncio.run(enrich_all_users())
