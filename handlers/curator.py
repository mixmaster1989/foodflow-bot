"""Handler module for Curator Dashboard functionality.

This module provides handlers for:
- Curator dashboard (view wards, stats)
- Ward list with filtering
- Individual ward detail view
- Broadcast messaging to wards
- Referral link generation
"""
import logging
from datetime import datetime, timedelta

from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, func

from config import settings
from database.base import get_db
from database.models import User, ConsumptionLog, UserSettings

router = Router()
logger = logging.getLogger(__name__)


class CuratorStates(StatesGroup):
    """FSM states for curator interactions."""
    composing_broadcast = State()
    composing_nudge = State()


@router.callback_query(F.data == "curator_dashboard")
async def curator_dashboard(callback: types.CallbackQuery) -> None:
    """Show curator dashboard with key metrics."""
    user_id = callback.from_user.id
    
    async for session in get_db():
        # Get curator's wards
        stmt = select(User).where(User.curator_id == user_id)
        wards = (await session.execute(stmt)).scalars().all()
        
        # Count active today (have logs today)
        today = datetime.utcnow().date()
        active_count = 0
        for ward in wards:
            log_stmt = select(ConsumptionLog).where(
                ConsumptionLog.user_id == ward.id,
                func.date(ConsumptionLog.date) == today
            ).limit(1)
            has_logs = (await session.execute(log_stmt)).scalar_one_or_none()
            if has_logs:
                active_count += 1
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🏆 Марафон", callback_data="curator_marathon_menu")
    builder.button(text="👥 Мои подопечные", callback_data="curator_wards:0")
    builder.button(text="📢 Рассылка", callback_data="curator_broadcast_start")
    builder.button(text="🔗 Моя ссылка", callback_data="curator_generate_link")
    builder.button(text="🔙 В меню", callback_data="main_menu")
    builder.adjust(1, 1, 2, 1)
    
    text = (
        f"👨‍🏫 <b>Кабинет Куратора</b>\n\n"
        f"👥 Подопечных: <b>{len(wards)}</b>\n"
        f"✅ Активны сегодня: <b>{active_count}</b>\n"
        f"😴 Не заполняли: <b>{len(wards) - active_count}</b>\n\n"
        f"<i>Выберите действие:</i>"
    )
    
    try:
        await callback.message.edit_caption(caption=text, parse_mode="HTML", reply_markup=builder.as_markup())
    except Exception:
        try:
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
        except Exception:
            await callback.message.delete()
            await callback.message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("curator_wards:"))
async def curator_ward_list(callback: types.CallbackQuery) -> None:
    """Show paginated list of wards with quick stats."""
    page = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    page_size = 10
    
    async for session in get_db():
        # Get curator's wards
        stmt = select(User).where(User.curator_id == user_id)
        all_wards = (await session.execute(stmt)).scalars().all()
        
        today = datetime.utcnow().date()
        ward_stats = []
        
        for ward in all_wards:
            # Get today's stats
            log_stmt = select(
                func.sum(ConsumptionLog.calories),
                func.sum(ConsumptionLog.protein)
            ).where(
                ConsumptionLog.user_id == ward.id,
                func.date(ConsumptionLog.date) == today
            )
            result = (await session.execute(log_stmt)).first()
            calories = int(result[0] or 0)
            protein = int(result[1] or 0)
            
            ward_stats.append({
                "id": ward.id,
                "name": ward.username or f"id:{ward.id}",
                "calories": calories,
                "protein": protein,
                "active": calories > 0
            })
    
    # Pagination
    total_pages = (len(ward_stats) + page_size - 1) // page_size
    start = page * page_size
    end = start + page_size
    page_wards = ward_stats[start:end]
    
    builder = InlineKeyboardBuilder()
    
    if not page_wards:
        text = "👥 <b>Подопечные</b>\n\nПока никого нет. Отправьте кому-нибудь вашу реферальную ссылку!"
    else:
        text = f"👥 <b>Подопечные ({len(ward_stats)})</b>\n\n"
        for w in page_wards:
            status = "✅" if w["active"] else "😴"
            text += f"{status} @{w['name']} — {w['calories']} ккал / {w['protein']}г б.\n"
            builder.button(text=f"👤 {w['name'][:15]}", callback_data=f"curator_ward:{w['id']}")
    
    # Pagination buttons
    nav_row = []
    if page > 0:
        nav_row.append(types.InlineKeyboardButton(text="⬅️", callback_data=f"curator_wards:{page-1}"))
    nav_row.append(types.InlineKeyboardButton(text=f"{page+1}/{max(1, total_pages)}", callback_data="noop"))
    if page < total_pages - 1:
        nav_row.append(types.InlineKeyboardButton(text="➡️", callback_data=f"curator_wards:{page+1}"))
    
    builder.adjust(2)
    if nav_row:
        builder.row(*nav_row)
    builder.button(text="🔙 Назад", callback_data="curator_dashboard")
    
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("curator_ward:"))
async def curator_ward_detail(callback: types.CallbackQuery) -> None:
    """Show detailed stats for a specific ward."""
    ward_id = int(callback.data.split(":")[1])
    
    async for session in get_db():
        ward = await session.get(User, ward_id)
        if not ward:
            await callback.answer("Пользователь не найден", show_alert=True)
            return
        
        # Get today's logs
        today = datetime.utcnow().date()
        log_stmt = select(ConsumptionLog).where(
            ConsumptionLog.user_id == ward_id,
            func.date(ConsumptionLog.date) == today
        ).order_by(ConsumptionLog.date.desc())
        logs = (await session.execute(log_stmt)).scalars().all()
        
        # Get user settings (goals)
        settings_stmt = select(UserSettings).where(UserSettings.user_id == ward_id)
        ward_settings = (await session.execute(settings_stmt)).scalar_one_or_none()
    
    # Calculate totals
    total_cal = sum(l.calories for l in logs)
    total_prot = sum(l.protein for l in logs)
    total_fat = sum(l.fat for l in logs)
    total_carbs = sum(l.carbs for l in logs)
    
    goal_cal = ward_settings.calorie_goal if ward_settings else 2000
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📩 Написать", callback_data=f"curator_nudge:{ward_id}")
    builder.button(text="🔙 К списку", callback_data="curator_wards:0")
    builder.adjust(2)
    
    text = (
        f"👤 <b>@{ward.username or ward_id}</b>\n\n"
        f"📅 <b>Сегодня:</b>\n"
        f"🔥 Калории: <b>{int(total_cal)}</b> / {goal_cal}\n"
        f"🥩 Белки: <b>{total_prot:.1f}</b>г\n"
        f"🥑 Жиры: <b>{total_fat:.1f}</b>г\n"
        f"🍞 Углеводы: <b>{total_carbs:.1f}</b>г\n\n"
    )
    
    if logs:
        text += "<b>Последние приёмы:</b>\n"
        for log in logs[:5]:
            time_str = log.date.strftime("%H:%M")
            text += f"🕐 {time_str} — {log.product_name} ({int(log.calories)} ккал)\n"
    else:
        text += "<i>Сегодня ничего не записывал</i>"
    
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "curator_generate_link")
async def curator_generate_link(callback: types.CallbackQuery) -> None:
    """Generate and display unique referral link for curator."""
    import uuid
    user_id = callback.from_user.id
    
    async for session in get_db():
        stmt = select(User).where(User.id == user_id)
        user = (await session.execute(stmt)).scalar_one_or_none()
        
        if not user:
            await callback.answer("Ошибка", show_alert=True)
            return
        
        # Generate token if not exists
        if not user.referral_token:
            user.referral_token = str(uuid.uuid4())[:8]
            await session.commit()
        
        token = user.referral_token
    
    # Get bot username
    bot_info = await callback.bot.get_me()
    bot_username = bot_info.username
    
    link = f"https://t.me/{bot_username}?start=ref_{token}"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="curator_dashboard")
    
    text = (
        f"🔗 <b>Ваша реферальная ссылка:</b>\n\n"
        f"<code>{link}</code>\n\n"
        f"Отправьте эту ссылку вашим подопечным. "
        f"Когда они зарегистрируются — автоматически станут вашими подопечными!"
    )
    
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("curator_nudge:"))
async def curator_nudge(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Prepare to send a reminder/nudge to a specific ward."""
    ward_id = int(callback.data.split(":")[1])
    await state.update_data(nudge_ward_id=ward_id)
    await state.set_state(CuratorStates.composing_nudge)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="curator_wards:0")
    
    text = (
        "📩 <b>Написать подопечному</b>\n\n"
        "Введите сообщение, которое будет отправлено от вашего имени:"
    )
    
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()


@router.message(CuratorStates.composing_nudge)
async def curator_send_nudge(message: types.Message, state: FSMContext) -> None:
    """Send the nudge message to ward."""
    data = await state.get_data()
    ward_id = data.get("nudge_ward_id")
    
    if not ward_id:
        await state.clear()
        return
    
    async for session in get_db():
        curator = await session.get(User, message.from_user.id)
        curator_name = curator.username if curator else "Куратор"
    
    try:
        from aiogram import Bot
        bot = Bot(token=settings.BOT_TOKEN)
        await bot.send_message(
            ward_id,
            f"📩 <b>Сообщение от куратора @{curator_name}:</b>\n\n{message.text}",
            parse_mode="HTML"
        )
        await bot.session.close()
        
        await message.answer("✅ Сообщение отправлено!")
    except Exception as e:
        await message.answer(f"❌ Не удалось отправить: {e}")
    
    await state.clear()


@router.callback_query(F.data == "curator_broadcast_start")
async def curator_broadcast_start(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Start broadcast composition."""
    await state.set_state(CuratorStates.composing_broadcast)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="curator_dashboard")
    
    text = (
        "📢 <b>Рассылка подопечным</b>\n\n"
        "Введите сообщение, которое будет отправлено ВСЕМ вашим подопечным:"
    )
    
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()


@router.message(CuratorStates.composing_broadcast)
async def curator_send_broadcast(message: types.Message, state: FSMContext) -> None:
    """Send broadcast message to all wards."""
    user_id = message.from_user.id
    
    async for session in get_db():
        curator = await session.get(User, user_id)
        curator_name = curator.username if curator else "Куратор"
        
        # Get all wards
        stmt = select(User).where(User.curator_id == user_id)
        wards = (await session.execute(stmt)).scalars().all()
    
    if not wards:
        await message.answer("❌ У вас нет подопечных для рассылки")
        await state.clear()
        return
    
    sent = 0
    failed = 0
    
    from aiogram import Bot
    bot = Bot(token=settings.BOT_TOKEN)
    
    for ward in wards:
        try:
            await bot.send_message(
                ward.id,
                f"📢 <b>Сообщение от куратора @{curator_name}:</b>\n\n{message.text}",
                parse_mode="HTML"
            )
            sent += 1
        except Exception:
            failed += 1
    
    await bot.session.close()
    await state.clear()
    
    await message.answer(f"✅ Рассылка завершена!\n\n📨 Доставлено: {sent}\n❌ Не доставлено: {failed}")
