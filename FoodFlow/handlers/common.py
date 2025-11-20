from aiogram import Router, types
from aiogram.filters import Command
from sqlalchemy.future import select
from FoodFlow.database.base import get_db
from FoodFlow.database.models import User

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
            
    # Create Main Menu Keyboard
    kb = [
        [types.KeyboardButton(text="🧊 Холодильник"), types.KeyboardButton(text="👨‍🍳 Рецепты")],
        [types.KeyboardButton(text="📊 Статистика")]
    ]
    keyboard = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

    await message.answer(
        "👋 Привет! Я FoodFlow.\n\n"
        "📸 **Скинь мне фото чека**, и я добавлю продукты в твой виртуальный холодильник.\n"
        "Или используй меню ниже:",
        reply_markup=keyboard
    )
