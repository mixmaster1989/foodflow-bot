"""Module for common handlers (start command, etc.).

Contains:
- cmd_start: Initial bot start handler that creates user if not exists
"""
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
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
            [KeyboardButton(text="🏠 Главное меню")]
        ],
        resize_keyboard=True,
        persistent=True
    )


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
    # TODO [CURATOR-1.2]: Parse deep link for referral token
    # Example: /start ref_abc123 -> extract "abc123"
    # args = message.text.split()[1] if len(message.text.split()) > 1 else None
    # if args and args.startswith("ref_"):
    #     referral_token = args[4:]
    #     -> find curator by token, link new user to curator_id
    
    async for session in get_db():
        stmt = select(User).where(User.id == message.from_user.id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            user = User(id=message.from_user.id, username=message.from_user.username)
            # TODO [CURATOR-1.2]: If referral token found, set user.curator_id here
            session.add(user)
            await session.commit()
            # TODO [CURATOR-1.2]: Notify curator about new ward

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
    await show_main_menu(message, message.from_user.first_name)


