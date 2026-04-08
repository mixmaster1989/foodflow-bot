import logging
from datetime import datetime, timedelta
import json

from aiogram import F, Router, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.base import get_db
from database.models import UserSettings, Subscription
from services.ai_guide import AIGuideService

router = Router()
logger = logging.getLogger(__name__)

class GuideOnboarding(StatesGroup):
    waiting_for_schedule = State()
    waiting_for_preferences = State()
    waiting_for_weak_spots = State()
    waiting_for_personality = State()

@router.message(Command("guide"))
@router.callback_query(F.data == "menu_guide")
async def show_guide_menu(target: types.Message | types.CallbackQuery, state: FSMContext):
    """Main menu for AI Guide."""
    user_id = target.from_user.id
    if isinstance(target, types.CallbackQuery):
        await target.answer()
        msg = target.message
    else:
        msg = target

    async for session in get_db():
        stmt = select(UserSettings).where(UserSettings.user_id == user_id)
        settings_obj = (await session.execute(stmt)).scalar_one_or_none()
        
        # Check if user has PRO
        sub_stmt = select(Subscription).where(Subscription.user_id == user_id)
        sub = (await session.execute(sub_stmt)).scalar_one_or_none()
        
        is_pro = sub and sub.tier == "pro" and sub.is_active
        is_active = settings_obj and settings_obj.guide_active_until and settings_obj.guide_active_until > datetime.now()
        
        builder = InlineKeyboardBuilder()
        
        if not is_pro:
            text = (
                "🤖 <b>Личный ИИ-Гид</b>\n\n"
                "Это продвинутый помощник, который:\n"
                "• Анализирует твой рацион в реальном времени\n"
                "• Дает персональные советы и предостережения\n"
                "• Мотивирует и помогает не сходить с пути\n\n"
                "⚠️ <i>Функция доступна только владельцам <b>PRO-подписки</b>.</i>"
            )
            builder.button(text="💎 Перейти на PRO", callback_data="menu_subscription")
        elif not is_active:
            text = (
                "🤖 <b>Личный ИИ-Гид</b>\n\n"
                "Твой персональный наставник готов к работе! Чтобы начать, нужно активировать функцию.\n\n"
                "💳 <b>Стоимость:</b> 300 ★ / месяц (поверх PRO)"
            )
            builder.button(text="🚀 Активировать Гида", callback_data="guide_activate_start")
        else:
            config = settings_obj.guide_config or {}
            personality = config.get("personality", "soft")
            pers_map = {"soft": "🌸 Поддерживающий", "hard": "🦾 Строгий", "direct": "📊 Аналитик"}
            
            text = (
                "🤖 <b>Твой Личный ИИ-Гид активен!</b>\n\n"
                f"🎭 <b>Характер:</b> {pers_map.get(personality, personality)}\n"
                f"📅 <b>Активен до:</b> {settings_obj.guide_active_until.strftime('%d.%m.%Y')}\n\n"
                "Я внимательно слежу за твоими логами и буду давать советы прямо в отчетах о еде."
            )
            builder.button(text="⚙️ Изменить характер", callback_data="guide_personality_choice")
            builder.button(text="📋 Перепройти анкету", callback_data="guide_onboarding_start")
        
        builder.button(text="🔙 Назад", callback_data="main_menu")
        builder.adjust(1)
        
        await msg.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())

@router.callback_query(F.data == "guide_activate_start")
async def guide_activate_mock(callback: types.CallbackQuery, state: FSMContext):
    """Mock activation for Guide (granting access for testing)."""
    user_id = callback.from_user.id
    
    async for session in get_db():
        stmt = select(UserSettings).where(UserSettings.user_id == user_id)
        settings_obj = (await session.execute(stmt)).scalar_one_or_none()
        
        if settings_obj:
            settings_obj.guide_active_until = datetime.now() + timedelta(days=30)
            await session.commit()
            
    await callback.answer("🎉 Функция активирована! (Тестовый период)", show_alert=True)
    await start_onboarding(callback, state)

@router.callback_query(F.data == "guide_onboarding_start")
async def start_onboarding(callback: types.CallbackQuery, state: FSMContext):
    """Start the onboarding questionnaire."""
    await callback.answer()
    await state.set_state(GuideOnboarding.waiting_for_schedule)
    
    await callback.message.answer(
        "📝 <b>Анкета Личного Гида (1/4)</b>\n\n"
        "Расскажи о своем распорядке дня. Во сколько ты обычно просыпаешься, завтракаешь и когда у тебя последний прием пищи?\n\n"
        "<i>Это поможет мне понимать, когда ты 'косячишь' с ночными перекусами.</i>",
        parse_mode="HTML"
    )

@router.message(GuideOnboarding.waiting_for_schedule)
async def process_schedule(message: types.Message, state: FSMContext):
    await state.update_data(schedule=message.text)
    await state.set_state(GuideOnboarding.waiting_for_preferences)
    await message.answer(
        "🍏 <b>Анкета (2/4)</b>\n\n"
        "Какие продукты ты просто обожаешь, а какие терпеть не можешь? Есть ли аллергии?\n\n"
        "<i>Буду учитывать это в советах.</i>",
        parse_mode="HTML"
    )

@router.message(GuideOnboarding.waiting_for_preferences)
async def process_preferences(message: types.Message, state: FSMContext):
    await state.update_data(preferences=message.text)
    await state.set_state(GuideOnboarding.waiting_for_weak_spots)
    await message.answer(
        "🍩 <b>Анкета (3/4)</b>\n\n"
        "Расскажи о своих 'слабых местах'. Срываешься ли ты на сладкое? Бывает ли лень готовить после работы?\n\n"
        "<i>В эти моменты я буду особенно тебя поддерживать.</i>",
        parse_mode="HTML"
    )

@router.message(GuideOnboarding.waiting_for_weak_spots)
async def process_weak_spots(message: types.Message, state: FSMContext):
    await state.update_data(weak_spots=message.text)
    await state.set_state(GuideOnboarding.waiting_for_personality)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🌸 Поддерживающий", callback_data="guide_pers:soft")
    builder.button(text="🦾 Строгий", callback_data="guide_pers:hard")
    builder.button(text="📊 Аналитик", callback_data="guide_pers:direct")
    builder.adjust(1)
    
    await message.answer(
        "🎭 <b>Анкета (4/4)</b>\n\n"
        "И последнее: какой характер мне выбрать?\n\n"
        "• <b>Поддерживающий:</b> буду хвалить и мягко направлять.\n"
        "• <b>Строгий:</b> буду честен и жесток, если халтуришь.\n"
        "• <b>Аналитик:</b> только факты, цифры и логика.",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )

@router.callback_query(F.data.startswith("guide_pers:"), GuideOnboarding.waiting_for_personality)
async def process_personality(callback: types.CallbackQuery, state: FSMContext):
    personality = callback.data.split(":")[1]
    data = await state.get_data()
    
    config = {
        "personality": personality,
        "answers": {
            "schedule": data.get("schedule"),
            "preferences": data.get("preferences"),
            "weak_spots": data.get("weak_spots")
        }
    }
    
    async for session in get_db():
        stmt = select(UserSettings).where(UserSettings.user_id == callback.from_user.id)
        settings_obj = (await session.execute(stmt)).scalar_one_or_none()
        if settings_obj:
            settings_obj.guide_config = config
            await session.commit()
            
    await state.clear()
    await callback.message.answer(
        "🎉 <b>Настройка завершена!</b>\n\n"
        "Теперь я твой официальный гид. Я буду приходить с советами после каждого лога еды. Попробуем?",
        parse_mode="HTML"
    )
    await show_guide_menu(callback, state)

@router.callback_query(F.data == "guide_personality_choice")
async def change_personality_quick(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    builder = InlineKeyboardBuilder()
    builder.button(text="🌸 Поддерживающий", callback_data="guide_set_pers:soft")
    builder.button(text="🦾 Строгий", callback_data="guide_set_pers:hard")
    builder.button(text="📊 Аналитик", callback_data="guide_set_pers:direct")
    builder.button(text="🔙 Назад", callback_data="menu_guide")
    builder.adjust(1)
    await callback.message.edit_text("🎭 Выбери мой характер:", reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("guide_set_pers:"))
async def save_personality_quick(callback: types.CallbackQuery, state: FSMContext):
    personality = callback.data.split(":")[1]
    async for session in get_db():
        stmt = select(UserSettings).where(UserSettings.user_id == callback.from_user.id)
        settings_obj = (await session.execute(stmt)).scalar_one_or_none()
        if settings_obj:
            config = settings_obj.guide_config or {}
            config["personality"] = personality
            settings_obj.guide_config = config
            await session.commit()
    await callback.answer("🎭 Характер изменен!")
    await show_guide_menu(callback, state)

# Helper to register router - will be called in main.py
def register_guide_handlers(main_router):
    main_router.include_router(router)
from sqlalchemy import select # Duplicate import for safety or fix main imports
