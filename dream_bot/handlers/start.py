from aiogram import Router, types
from aiogram.filters import Command
from sqlalchemy import select
from database.base import SessionLocal
from database.models import User

router = Router()

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    args = message.text.split()
    referrer_id = None
    if len(args) > 1:
        try:
            referrer_id = int(args[1])
        except:
            pass

    async with SessionLocal() as session:
        user = await session.get(User, message.from_user.id)
        if not user:
            user = User(id=message.from_user.id, username=message.from_user.username, invited_by=referrer_id)
            session.add(user)
            
            # Если есть реферер, даем ему бонус
            if referrer_id:
                referrer = await session.get(User, referrer_id)
                if referrer:
                    referrer.dreams_balance += 1
            
            await session.commit()

    ref_link = f"https://t.me/{(await message.bot.get_me()).username}?start={message.from_user.id}"
    
    welcome_text = (
        "🌌 <b>Приветствую тебя в Обители Снов!</b>\n\n"
        "Я — твой персональный ИИ-Толкователь. Расскажи мне свой сон (текстом или голосом), "
        "и я открою тебе его тайный смысл.\n\n"
        f"🎁 Тебе доступно <b>1 бесплатное толкование</b>.\n\n"
        f"🔗 <b>Твоя реферальная ссылка:</b> <code>{ref_link}</code>\n"
        "(Пригласи друга и получи +1 сон бесплатно!)"
    )
    await message.answer(welcome_text, parse_mode="HTML")
