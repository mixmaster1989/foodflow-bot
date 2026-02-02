"""
Middleware for automatic user profile enrichment.

This middleware runs on EVERY message/callback and updates user profile
with fresh Telegram data: first_name, last_name, username, language_code, is_premium.
"""

from datetime import datetime
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from sqlalchemy import select

from database.base import async_session
from database.models import User


class UserEnrichmentMiddleware(BaseMiddleware):
    """Middleware that enriches user profile data on every interaction."""
    
    async def __call__(self, handler, event: TelegramObject, data: dict):
        # Get user from event
        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user
        
        if user:
            await self._enrich_user(user)
        
        return await handler(event, data)
    
    async def _enrich_user(self, tg_user):
        """Update user profile with Telegram data."""
        async with async_session() as session:
            # Get existing user
            db_user = await session.get(User, tg_user.id)
            
            if not db_user:
                return  # User will be created elsewhere (auth handler)
            
            # Update fields if changed
            changed = False
            
            if db_user.username != tg_user.username:
                db_user.username = tg_user.username
                changed = True
            
            if db_user.first_name != tg_user.first_name:
                db_user.first_name = tg_user.first_name
                changed = True
            
            if db_user.last_name != tg_user.last_name:
                db_user.last_name = tg_user.last_name
                changed = True
            
            if db_user.language_code != tg_user.language_code:
                db_user.language_code = tg_user.language_code
                changed = True
            
            if hasattr(tg_user, 'is_premium') and db_user.is_premium != (tg_user.is_premium or False):
                db_user.is_premium = tg_user.is_premium or False
                changed = True
            
            # Always update last_activity
            db_user.last_activity = datetime.utcnow()
            
            if changed:
                await session.commit()
