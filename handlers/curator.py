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

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, select

from config import settings
from database.base import get_db
from database.models import ConsumptionLog, User, UserSettings, WaterLog
from utils.user import get_user_display_long, get_user_display_name

router = Router()
logger = logging.getLogger(__name__)


class CuratorStates(StatesGroup):
    """FSM states for curator interactions."""
    composing_broadcast = State()
    composing_nudge = State()
    entering_link_days = State()


@router.callback_query(F.data == "curator_dashboard")
async def curator_dashboard(callback: types.CallbackQuery) -> None:
    """Show curator dashboard with key metrics."""
    user_id = callback.from_user.id

    async for session in get_db():
        # Get curator's wards
        stmt = select(User).where(User.curator_id == user_id)
        wards = (await session.execute(stmt)).scalars().all()

        # Count active today (have logs today)
        today = datetime.now().date()
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

        today = datetime.now().date()
        ward_stats = []

        for ward in all_wards:
            # Get today's stats
            log_stmt = select(
                func.sum(ConsumptionLog.calories),
                func.sum(ConsumptionLog.protein),
                func.sum(ConsumptionLog.fiber)
            ).where(
                ConsumptionLog.user_id == ward.id,
                func.date(ConsumptionLog.date) == today
            )
            result = (await session.execute(log_stmt)).first()
            calories = int(result[0] or 0)
            protein = int(result[1] or 0)
            fiber = int(result[2] or 0)

            ward_stats.append({
                "id": ward.id,
                "name": get_user_display_name(ward),
                "calories": calories,
                "protein": protein,
                "fiber": fiber,
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
            text += f"{status} @{w['name']} — {w['calories']} ккал / {w['protein']}г б. | {w['fiber']}г кл.\n"
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
    """Show detailed stats for a specific ward with date navigation."""
    parts = callback.data.split(":")
    ward_id = int(parts[1])

    # Check if date is provided
    target_date = datetime.now().date()
    if len(parts) > 2:
        try:
            target_date = datetime.strptime(parts[2], "%Y-%m-%d").date()
        except ValueError:
            pass

    async for session in get_db():
        ward = await session.get(User, ward_id)
        if not ward:
            await callback.answer("Пользователь не найден", show_alert=True)
            return

        # Get logs for TARGET date
        log_stmt = select(ConsumptionLog).where(
            ConsumptionLog.user_id == ward_id,
            func.date(ConsumptionLog.date) == target_date
        ).order_by(ConsumptionLog.date.desc())
        logs = (await session.execute(log_stmt)).scalars().all()

        # Get user settings (goals)
        settings_stmt = select(UserSettings).where(UserSettings.user_id == ward_id)
        ward_settings = (await session.execute(settings_stmt)).scalar_one_or_none()

        # Get water for TARGET date
        water_stmt = select(func.sum(WaterLog.amount_ml)).where(
            WaterLog.user_id == ward_id,
            func.date(WaterLog.date) == target_date
        )
        water_total = (await session.execute(water_stmt)).scalar() or 0

    # Calculate totals
    total_cal = sum(l.calories for l in logs)
    total_prot = sum(l.protein for l in logs)
    total_fat = sum(l.fat for l in logs)
    total_carbs = sum(l.carbs for l in logs)
    total_fiber = sum(l.fiber for l in logs) # NEW: Fiber

    goal_cal = ward_settings.calorie_goal if ward_settings else 2000

    builder = InlineKeyboardBuilder()

    # 1. Navigation Row
    prev_date = target_date - timedelta(days=1)
    next_date = target_date + timedelta(days=1)

    today = datetime.now().date()
    is_today = (target_date == today)

    nav_row = []
    prev_label = "⬅️ Вчера" if is_today else "⬅️"
    nav_row.append(types.InlineKeyboardButton(text=prev_label, callback_data=f"curator_ward:{ward_id}:{prev_date}"))

    date_label = "Сегодня" if is_today else target_date.strftime("%d.%m")
    nav_row.append(types.InlineKeyboardButton(text=f"📅 {date_label}", callback_data="noop"))

    if not is_today:
        nav_row.append(types.InlineKeyboardButton(text="➡️", callback_data=f"curator_ward:{ward_id}:{next_date}"))

    builder.row(*nav_row)

    # 2. Action buttons
    if logs:
         builder.button(text="📜 Весь список", callback_data=f"curator_ward_logs:{ward_id}:0:{target_date}")

    builder.button(text="📩 Написать", callback_data=f"curator_nudge:{ward_id}")
    builder.button(text="🗑 Удалить", callback_data=f"curator_remove_ward:{ward_id}")
    builder.button(text="🔙 К списку", callback_data="curator_wards:0")

    # Adjust remaining rows (1 button per row basically)
    builder.adjust(1) # This applies to buttons added via .button()
    # But row() added buttons stay as is.

    # Generate Image
    from services.image_renderer import draw_daily_card

    # Pack data for renderer
    total_metrics = {
        "calories": total_cal,
        "protein": total_prot,
        "fat": total_fat,
        "carbs": total_carbs,
        "fiber": total_fiber
    }
    goals = {
        "calories": goal_cal,
        "water": ward_settings.water_goal if ward_settings else 2000
    }

    # We need to run this in executor to avoid blocking event loop
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    # Run image gen in thread
    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor() as pool:
        bio = await loop.run_in_executor(
            pool,
            draw_daily_card,
            get_user_display_name(ward),
            target_date,
            logs,
            total_metrics,
            goals,
            water_total
        )

    from aiogram.types import BufferedInputFile, InputMediaPhoto
    photo_file = BufferedInputFile(bio.getvalue(), filename="summary.png")

    caption = (
        f"👤 <b>{get_user_display_long(ward)}</b>\n"
        f"📅 <b>{target_date.strftime('%d.%m.%Y')}</b>"
    )

    try:
        # Try to edit existing photo
        await callback.message.edit_media(
            media=InputMediaPhoto(media=photo_file, caption=caption, parse_mode="HTML"),
            reply_markup=builder.as_markup()
        )
    except Exception:
        # If text message, delete and send photo
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer_photo(
            photo=photo_file,
            caption=caption,
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )

    await callback.answer()
    await callback.answer()

@router.callback_query(F.data.startswith("curator_remove_ward:"))
async def curator_remove_ward_confirm(callback: types.CallbackQuery) -> None:
    """Show confirmation for removing a ward."""
    ward_id = int(callback.data.split(":")[1])

    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, удалить", callback_data=f"curator_do_remove_ward:{ward_id}")
    builder.button(text="🔙 Отмена", callback_data=f"curator_ward:{ward_id}")
    builder.adjust(1)

    text = (
        "⚠️ <b>Вы уверены?</b>\n\n"
        "Вы перестанете быть куратором этого пользователя. "
        "Вся его история останется, но он станет обычным пользователем."
    )

    try:
         await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    except Exception:
         await callback.message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("curator_do_remove_ward:"))
async def curator_do_remove_ward(callback: types.CallbackQuery) -> None:
    """Execute ward removal."""
    ward_id = int(callback.data.split(":")[1])
    curator_name = callback.from_user.username or "Ваш куратор"

    async for session in get_db():
        ward = await session.get(User, ward_id)
        if ward:
            ward.curator_id = None
            await session.commit()

    # Notify ward
    try:
        from aiogram import Bot
        bot = Bot(token=settings.BOT_TOKEN)
        await bot.send_message(
            ward_id,
            f"ℹ️ Куратор @{curator_name} прекратил работу с вами.\nВы переведены в режим самостоятельного использования бота."
        )
        await bot.session.close()
    except Exception as e:
        logger.error(f"Failed to notify ward {ward_id} of removal: {e}")

    await callback.answer("✅ Подопечный удален.", show_alert=True)
    # Go back to wards list
    callback.data = "curator_wards:0"
    await curator_ward_list(callback)


@router.callback_query(F.data.startswith("curator_ward_logs:"))
async def curator_ward_logs_list(callback: types.CallbackQuery) -> None:
    """Show paginated list of ward logs for specific date."""
    parts = callback.data.split(":")
    ward_id = int(parts[1])
    page = int(parts[2])

    # Handle optional date
    if len(parts) > 3:
        try:
            target_date = datetime.strptime(parts[3], "%Y-%m-%d").date()
        except ValueError:
            target_date = datetime.now().date()
    else:
        target_date = datetime.now().date()

    page_size = 10

    async for session in get_db():
        ward = await session.get(User, ward_id)
        if not ward:
            await callback.answer("Пользователь не найден")
            return

        log_stmt = select(ConsumptionLog).where(
            ConsumptionLog.user_id == ward_id,
            func.date(ConsumptionLog.date) == target_date
        ).order_by(ConsumptionLog.date.desc())
        all_logs = (await session.execute(log_stmt)).scalars().all()

    total_pages = (len(all_logs) + page_size - 1) // page_size
    start = page * page_size
    end = start + page_size
    page_logs = all_logs[start:end]

    date_str = target_date.strftime('%d.%m.%Y')

    text = (
        f"📜 <b>Еда за {date_str}: {get_user_display_name(ward)}</b>\n"
        f"Страница {page + 1}/{max(1, total_pages)}\n\n"
    )

    for log in page_logs:
        time_str = log.date.strftime("%H:%M")
        text += f"• <code>{time_str}</code> <b>{log.product_name}</b>\n"
        fiber_str = f" Кл:{log.fiber:.1f}" if log.fiber else ""
        text += f"  └ {int(log.calories)} ккал | Б:{log.protein:.1f} Ж:{log.fat:.1f} У:{log.carbs:.1f}{fiber_str}\n"

    builder = InlineKeyboardBuilder()

    # Pagination buttons
    nav_row = []
    if page > 0:
        nav_row.append(types.InlineKeyboardButton(text="⬅️", callback_data=f"curator_ward_logs:{ward_id}:{page-1}:{target_date}"))
    if page < total_pages - 1:
        nav_row.append(types.InlineKeyboardButton(text="➡️", callback_data=f"curator_ward_logs:{ward_id}:{page+1}:{target_date}"))

    if nav_row:
        builder.row(*nav_row)

    builder.button(text="🔙 К карточке", callback_data=f"curator_ward:{ward_id}:{target_date}")
    # builder.adjust logic handled by explicit row() above and then add()

    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(F.data == "curator_generate_link")
async def curator_generate_link(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Prompt for referral link expiration days."""
    builder = InlineKeyboardBuilder()
    builder.button(text="1 день", callback_data="curator_link_days:1")
    builder.button(text="7 дней", callback_data="curator_link_days:7")
    builder.button(text="14 дней", callback_data="curator_link_days:14")
    builder.button(text="30 дней", callback_data="curator_link_days:30")
    builder.button(text="Безлимит", callback_data="curator_link_days:0")
    builder.button(text="🔙 Назад", callback_data="curator_dashboard")
    builder.adjust(2, 2, 1, 1)

    await state.set_state(CuratorStates.entering_link_days)

    text = (
        "🔗 <b>Генерация реферальной ссылки</b>\n\n"
        "На сколько дней создать ссылку? После истечения срока "
        "новые подопечные не смогут по ней зарегистрироваться."
    )

    try:
         await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    except Exception:
         await callback.message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(F.data.startswith("curator_link_days:"))
@router.message(CuratorStates.entering_link_days)
async def curator_link_custom_days(event, state: FSMContext) -> None:
    """Handle custom days input or quick button for referral link."""
    await state.clear()

    days = 0
    if isinstance(event, types.CallbackQuery):
        days = int(event.data.split(":")[1])
        user_id = event.from_user.id
        callback = event
    else:
        try:
            days = int(event.text)
            if not (1 <= days <= 365):
                raise ValueError
        except ValueError:
            await event.answer("⚠️ Пожалуйста, введите число от 1 до 365, или используйте кнопки выше.")
            return
        user_id = event.from_user.id
        callback = None

    import uuid
    async for session in get_db():
        stmt = select(User).where(User.id == user_id)
        user = (await session.execute(stmt)).scalar_one_or_none()

        if not user:
            if callback:
                await callback.answer("Ошибка", show_alert=True)
            return

        # Always generate a NEW token and invalidate the old one
        user.referral_token = str(uuid.uuid4())[:12]

        if days == 0:
            user.referral_token_expires_at = None
        else:
            user.referral_token_expires_at = datetime.now() + timedelta(days=days)

        await session.commit()
        token = user.referral_token
        expires = user.referral_token_expires_at

    # Get bot username
    if callback:
        bot_info = await callback.bot.get_me()
    else:
        bot_info = await event.bot.get_me()

    bot_username = bot_info.username
    link = f"https://t.me/{bot_username}?start=ref_{token}"

    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="curator_dashboard")

    exp_text = "<b>Бессрочно</b>"
    if expires:
        # User local time approximation or just UTC label
        exp_text = f"до <b>{expires.strftime('%d.%m.%Y %H:%M')} (UTC)</b>"

    text = (
        f"🔗 <b>Ваша реферальная ссылка:</b>\n"
        f"Действительна: {exp_text}\n\n"
        f"<code>{link}</code>\n\n"
        f"Отправьте эту ссылку вашим подопечным. (Предыдущие ссылки больше недействительны)"
    )

    if callback:
        try:
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
        except Exception:
            await callback.message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
        await callback.answer()
    else:
        await event.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("curator_nudge:"))
async def curator_nudge(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Prepare to send a reminder/nudge to a specific ward (Chat Mode)."""
    ward_id = int(callback.data.split(":")[1])

    # Get ward info for display
    async for session in get_db():
        ward = await session.get(User, ward_id)
        ward_name = get_user_display_name(ward) if ward else "Подопечным"

    await state.update_data(nudge_ward_id=ward_id)
    await state.set_state(CuratorStates.composing_nudge)

    builder = InlineKeyboardBuilder()
    builder.button(text="🛑 Завершить переписку", callback_data="curator_stop_nudge")

    text = (
        f"✏️ <b>Режим переписки: {ward_name}</b>\n\n"
        f"⬇️ Все, что вы напишите ниже, будет мгновенно отправлено.\n"
        f"⬆️ Лог еды остался сверху."
    )

    # Send NEW message, do not edit the food log
    await callback.message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(F.data == "curator_stop_nudge")
async def curator_stop_nudge(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Exit chat mode."""
    await state.clear()
    await callback.message.edit_text("✅ <b>Переписка завершена.</b>", parse_mode="HTML")
    await callback.answer()

@router.message(CuratorStates.composing_nudge)
async def curator_send_nudge(message: types.Message, state: FSMContext) -> None:
    """Send the nudge message to ward (Persistent). Supports Text, Voice, Photo."""
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

        # Add Reply button for Ward
        reply_markup = InlineKeyboardBuilder()
        reply_markup.button(text="↩️ Ответить", callback_data=f"ward_reply:{message.from_user.id}")

        content_type = message.content_type
        text_to_send = message.text

        if content_type == "voice":
            status_msg = await message.answer("🎤 <i>Распознаю голос...</i>", parse_mode="HTML")
            try:
                import os

                from services.voice_stt import SpeechToText
                stt_engine = SpeechToText()

                file_info = await bot.get_file(message.voice.file_id)
                temp_dir = "services/temp"
                os.makedirs(temp_dir, exist_ok=True)
                ogg_path = f"{temp_dir}/nudge_voice_{message.voice.file_id}.ogg"

                await bot.download_file(file_info.file_path, ogg_path)
                text_to_send = await stt_engine.process_voice_message(ogg_path)

                try:
                    os.remove(ogg_path)
                except Exception:
                    pass

                if not text_to_send:
                    await status_msg.edit_text("❌ Не удалось распознать голос.")
                    return

                await status_msg.delete()
            except Exception as e:
                await message.answer(f"❌ Ошибка STT: {e}")
                return

        if content_type in ["text", "voice"]:
            # Send as text (either original or transcribed)
            prefix = "🎤 " if content_type == "voice" else "📩 "
            await bot.send_message(
                ward_id,
                f"{prefix}<b>Сообщение от куратора @{curator_name}:</b>\n\n{text_to_send}",
                parse_mode="HTML",
                reply_markup=reply_markup.as_markup()
            )
            await message.answer(f"✅ Отправлено: <i>{text_to_send}</i>", parse_mode="HTML")

        elif content_type == "photo":
            photo = message.photo[-1].file_id
            caption = f"📸 <b>Сообщение от куратора @{curator_name}:</b>\n\n{message.caption or ''}"
            await bot.send_photo(
                ward_id,
                photo=photo,
                caption=caption,
                parse_mode="HTML",
                reply_markup=reply_markup.as_markup()
            )
            await message.answer("✅ Фото отправлено!")

        else:
            await message.answer(f"⚠️ Тип сообщения {content_type} пока не поддерживается в режиме чата.")

        await bot.session.close()
        # Do NOT clear state!
    except Exception as e:
        await message.answer(f"❌ Не удалось отправить: {e}")


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
