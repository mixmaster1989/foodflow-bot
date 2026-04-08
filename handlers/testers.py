import logging
from datetime import datetime, timedelta
from aiogram import Router, types, F
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models import UserSettings
from database.base import async_session
import json

router = Router()
logger = logging.getLogger(__name__)

@router.callback_query(F.data == "guide_test:accept")
async def process_guide_test_accept(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    # 1. Provide PRO Guide for 30 days
    async with async_session() as session:
        stmt = select(UserSettings).where(UserSettings.user_id == user_id)
        settings = (await session.execute(stmt)).scalar_one_or_none()
        
        if not settings:
            settings = UserSettings(user_id=user_id)
            session.add(settings)
            
        settings.guide_active_until = datetime.now() + timedelta(days=30)
        
        # optionally set default values if None
        if not settings.guide_config:
            settings.guide_config = {"personality": "soft", "answers": {"preferences": "Люблю пробовать новое. Бета-тестер."}}
            
        await session.commit()
    
    # 2. Inform the user
    text = (
        "🎉 <b>Добро пожаловать в команду тестировщиков!</b>\n\n"
        "Я выдал тебе доступ к PRO ИИ-Гиду на 30 дней.\n"
        "Начиная с этого момента, старайся записывать всё, что ешь, отмечать воду и взвешиваться.\n"
        "Гид будет анализировать это и помогать тебе классными советами.\n\n"
        "<i>Погнали! Напиши мне что-то из еды, когда будешь готов.</i>"
    )
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer("Гид активирован!")

@router.callback_query(F.data == "guide_test:decline")
async def process_guide_test_decline(callback: types.CallbackQuery):
    text = (
        "Без проблем! Я всё понимаю. 💙\n"
        "Если когда-нибудь появится время и желание — дай знать. А пока продолжаем работу в твоем удобном темпе!"
    )
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer("Удачного дня!")
