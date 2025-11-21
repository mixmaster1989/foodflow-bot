from aiogram import Router, types
from aiogram.filters import Command
from sqlalchemy.future import select
from FoodFlow.database.base import get_db
from FoodFlow.database.models import User
from FoodFlow.handlers.menu import show_main_menu

router = Router()

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    async for session in get_db():
        stmt = select(User).where(User.id == message.from_user.id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            user = User(id=message.from_user.id, username=message.from_user.username)
            session.add(user)
            await session.commit()
            
    await show_main_menu(message, message.from_user.first_name)

