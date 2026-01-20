from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message, Update, ReplyKeyboardMarkup, KeyboardButton
from sqlalchemy.future import select

from config import settings
from database.base import get_db
from database.models import User
from handlers.menu import show_main_menu


class AuthMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any],
    ) -> Any:
        
        # Determine user_id and message object for reply
        user_id = None
        message_obj = None

        if event.message:
            user_id = event.message.from_user.id
            message_obj = event.message
        elif event.callback_query:
            user_id = event.callback_query.from_user.id
            message_obj = event.callback_query.message
        
        if not user_id:
            return await handler(event, data)

        async for session in get_db():
            # Get user from DB
            stmt = select(User).where(User.id == user_id)
            user = (await session.execute(stmt)).scalar_one_or_none()

            # If user not found (first start), let them pass to cmd_start (which checks logic)
            # BUT cmd_start creates user. 
            # We want to BLOCK everything until password.
            # If user usually gets created in cmd_start, we might face issue if we block start.
            
            # Allow /start if user doesn't exist? 
            # If user sends /start, we want to ask for password.
            
            if not user:
                # If user doesn't exist, we probably shouldn't block yet, OR we treat them as unverified.
                # Let's say we enforce password for EVERYONE.
                # If they send 'Welcome2026', we create them/verify them.
                pass
            
            # Check verification
            is_verified = user.is_verified if user else False

            if is_verified:
                return await handler(event, data)

            # --- Auth Logic ---

            # Helper for keyboard
            kb = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="🏠 Главное меню")]],
                resize_keyboard=True,
                persistent=True
            )
            
            # Only handle handle text messages for password input
            if event.message and event.message.text:
                text = event.message.text.strip()
                
                # Check Global Password (New Users)
                if text == settings.GLOBAL_PASSWORD:
                    if not user:
                        # Create user if not exists
                        user = User(id=user_id, username=event.message.from_user.username, is_verified=True)
                        session.add(user)
                    else:
                        user.is_verified = True
                    
                    await session.commit()
                    await message_obj.answer("✅ Пароль принят! Добро пожаловать.", reply_markup=kb)
                    # Show main menu immediately
                    await show_main_menu(message_obj, message_obj.from_user.first_name, message_obj.from_user.id)
                    return # Stop propagation (we handled it)

                # Check Personal Password (Old Users): MYSELF{id}
                expected_personal = f"MYSELF{user_id}"
                if text == expected_personal:
                    if not user:
                         # Should not happen for old users, but if so...
                        user = User(id=user_id, username=event.message.from_user.username, is_verified=True)
                        session.add(user)
                    else:
                        user.is_verified = True
                    
                    await session.commit()
                    await message_obj.answer("✅ Личный пароль принят!", reply_markup=kb)
                    # Show main menu immediately
                    await show_main_menu(message_obj, message_obj.from_user.first_name, message_obj.from_user.id)
                    return # Stop propagation

            # If we are here, user is not verified and didn't guess password.
            # Block access.
            if message_obj:
                # Avoid spamming on every update? 
                # Only answer if it's a message.
                if event.message:
                    await message_obj.answer(
                        "🔒 <b>Доступ ограничен</b>\n\n"
                        "Бот перешел в закрытый режим тестирования.\n"
                        "Введите пароль для продолжения.",
                        parse_mode="HTML"
                    )
            
            # Stop propagation
            return
