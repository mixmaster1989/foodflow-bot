"""Module for common handlers (start command, etc.).

Contains:
- cmd_start: Initial bot start handler that creates user if not exists
"""
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from sqlalchemy.future import select

from database.base import get_db
from database.models import User, UserSettings
from handlers.menu import show_main_menu
from handlers.onboarding import start_onboarding

router = Router()



def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Create persistent main menu keyboard."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🏠 Главное меню")
            ]
        ],
        resize_keyboard=True,
        persistent=True
    )


@router.message(F.text == "🏠 Главное меню")
async def btn_main_menu(message: types.Message, state: FSMContext):
    """Handle '🏠 Главное меню' button click by routing to /start logic."""
    await cmd_start(message, state)


@router.message(Command("webapp"))
async def cmd_webapp(message: types.Message):
    """Send Inline Button for Web App (More reliable initData)."""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Open FoodFlow", web_app=types.WebAppInfo(url="https://tretyakov-igor.tech/foodflow/"))]
    ])
    await message.answer("👇 Попробуй открыть через эту кнопку (Inline):", reply_markup=kb)


@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext) -> None:
    """Handle /start command - initialize user and show main menu or onboarding.

    Creates a new user in the database if they don't exist,
    then checks if onboarding is completed. If not - starts onboarding,
    otherwise shows main menu.

    Args:
        message: Telegram message object with /start command
        state: FSM context

    Returns:
        None

    """
    # Parse deep link for referral token: /start ref_abc123
    referral_token = None
    curator = None
    if len(message.text.split()) > 1:
        args = message.text.split()[1]
        if args.startswith("ref_"):
            referral_token = args[4:]
    
    async for session in get_db():
        # If referral token provided, find the curator
        if referral_token:
            curator_stmt = select(User).where(User.referral_token == referral_token)
            curator = (await session.execute(curator_stmt)).scalar_one_or_none()
        
        stmt = select(User).where(User.id == message.from_user.id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            # Create new user, optionally linked to curator
            user = User(
                id=message.from_user.id, 
                username=message.from_user.username,
                curator_id=curator.id if curator else None
            )
            session.add(user)
            await session.commit()
            
            # Notify curator about new ward
            if curator:
                from aiogram import Bot
                from config import settings
                bot = Bot(token=settings.BOT_TOKEN)
                try:
                    await bot.send_message(
                        curator.id,
                        f"🎉 <b>Новый подопечный!</b>\n\n"
                        f"К вам присоединился: @{message.from_user.username or 'Пользователь'}",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
                await bot.session.close()
        else:
            # User exists - check if we should link to curator
            # Only link if user has no curator yet and referral token provided
            if curator and not user.curator_id:
                user.curator_id = curator.id
                await session.commit()
                
                # Notify curator about new ward
                from aiogram import Bot
                from config import settings
                bot = Bot(token=settings.BOT_TOKEN)
                try:
                    await bot.send_message(
                        curator.id,
                        f"🎉 <b>Новый подопечный!</b>\n\n"
                        f"К вам присоединился: @{message.from_user.username or 'Пользователь'}",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
                await bot.session.close()

        # Check if user has completed onboarding
        settings_stmt = select(UserSettings).where(UserSettings.user_id == message.from_user.id)
        settings_result = await session.execute(settings_stmt)
        settings = settings_result.scalar_one_or_none()

        if not settings or not settings.is_initialized:
            # Start onboarding
            await start_onboarding(message, state)
            return

    # Send a separate message to force the ReplyKeyboard to appear
    await message.answer(
        "Загружаю меню...", 
        reply_markup=get_main_keyboard()
    )
    # Then show the visual menu (which will edit/send the photo)
    await show_main_menu(message, message.from_user.first_name, message.from_user.id)


