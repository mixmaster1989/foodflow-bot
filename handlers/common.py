"""Module for common handlers (start command, etc.).

Contains:
- cmd_start: Initial bot start handler that creates user if not exists
"""
from aiogram import Router, types
from aiogram.filters import Command
from sqlalchemy.future import select

from database.base import get_db
from database.models import User
from handlers.menu import show_main_menu

router = Router()


@router.message(Command("start"))
async def cmd_start(message: types.Message) -> None:
    """Handle /start command - initialize user and show main menu.

    Creates a new user in the database if they don't exist,
    then displays the main menu.

    Args:
        message: Telegram message object with /start command

    Returns:
        None

    """
    async for session in get_db():
        stmt = select(User).where(User.id == message.from_user.id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            user = User(id=message.from_user.id, username=message.from_user.username)
            session.add(user)
            await session.commit()

    await show_main_menu(message, message.from_user.first_name)

