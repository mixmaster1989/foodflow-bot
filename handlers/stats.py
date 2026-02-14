"""Module for statistics and consumption tracking handlers.

Contains:
- show_stats_menu: Display daily nutrition statistics
- stats_placeholder: Placeholder for future stats features
"""
from datetime import date, datetime, timedelta

from aiogram import F, Router, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, select

from database.base import get_db
from database.models import ConsumptionLog

router = Router()


@router.callback_query(F.data.startswith("menu_stats"))
async def show_stats_menu(callback: types.CallbackQuery) -> None:
    """Display daily nutrition statistics with date navigation."""
    parts = callback.data.split(":")
    
    # Check if date is provided
    target_date = datetime.utcnow().date()
    if len(parts) > 1:
        try:
            target_date = datetime.strptime(parts[1], "%Y-%m-%d").date()
        except ValueError:
            pass
            
    user_id: int = callback.from_user.id
    
    async for session in get_db():
        # Get consumption for TARGET date
        stmt = select(ConsumptionLog).where(
            ConsumptionLog.user_id == user_id,
            func.date(ConsumptionLog.date) == target_date
        )
        logs = (await session.execute(stmt)).scalars().all()

        # Calculate totals
        total_calories = sum(log.calories for log in logs) if logs else 0
        total_protein = sum(log.protein for log in logs) if logs else 0
        total_fat = sum(log.fat for log in logs) if logs else 0
        total_carbs = sum(log.carbs for log in logs) if logs else 0
        total_fiber = sum(log.fiber for log in logs if log.fiber) if logs else 0

        # Build response
        date_label = target_date.strftime('%d.%m.%Y')
        if target_date == datetime.utcnow().date():
            date_label += " (Сегодня)"
            
        if not logs:
            response = (
                f"📊 <b>Статистика за {date_label}</b>\n\n"
                "Пока нет данных.\n"
                "<i>Нажмите 🍽️ на продукты в холодильнике, чтобы отметить что съел!</i>"
            )
        else:
            response = (
                f"📊 <b>Твоя статистика за {date_label}</b>\n\n"
                f"🔥 Калории: <b>{total_calories:.0f}</b> ккал\n"
                f"🥩 Белки: <b>{total_protein:.1f}</b>г\n"
                f"🥑 Жиры: <b>{total_fat:.1f}</b>г\n"
                f"🍞 Углеводы: <b>{total_carbs:.1f}</b>г\n"
                f"{f'🥬 Клетчатка: <b>{total_fiber:.1f}</b>г' + chr(10) if total_fiber else ''}"
                f"\n📝 Приёмов пищи: <b>{len(logs)}</b>\n"
            )

    builder = InlineKeyboardBuilder()
    
    # Navigation Row
    prev_date = target_date - timedelta(days=1)
    next_date = target_date + timedelta(days=1)
    today = datetime.utcnow().date()
    
    nav_row = []
    nav_row.append(types.InlineKeyboardButton(text="⬅️", callback_data=f"menu_stats:{prev_date}"))
    if target_date != today:
        nav_row.append(types.InlineKeyboardButton(text="Сегодня", callback_data=f"menu_stats:{today}"))
        nav_row.append(types.InlineKeyboardButton(text="➡️", callback_data=f"menu_stats:{next_date}"))
        
    builder.row(*nav_row)

    if logs:
        builder.button(text="📋 Подробно", callback_data=f"stats_detailed:{target_date}")
        builder.button(text="📝 История", callback_data=f"stats_history:{target_date}")
    
    if target_date == today:
         builder.button(text="🗓️ Неделя", callback_data="stats_week")
         
    builder.button(text="🔙 Назад", callback_data="main_menu")
    builder.adjust(1) # Apply to added buttons, row() stays as is

    # Image path
    photo_path = types.FSInputFile("assets/stats.png")

    # Try to edit if possible (if previous was photo), otherwise send new
    try:
        await callback.message.edit_media(
            media=types.InputMediaPhoto(media=photo_path, caption=response, parse_mode="HTML"),
            reply_markup=builder.as_markup()
        )
    except Exception:
        # If edit fails (e.g. previous was text), delete and send new photo
        await callback.message.delete()
        await callback.message.answer_photo(
            photo=photo_path,
            caption=response,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data == "stats_detailed")
async def stats_detailed_handler(callback: types.CallbackQuery) -> None:
    """Show detailed report with timestamps for each meal."""
    from services.reports import generate_detailed_report
    
    user_id = callback.from_user.id
    report = await generate_detailed_report(user_id)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="menu_stats")
    
    try:
        await callback.message.edit_caption(
            caption=report,
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
    except Exception:
        try:
            await callback.message.edit_text(
                report,
                parse_mode="HTML",
                reply_markup=builder.as_markup()
            )
        except Exception:
            await callback.message.delete()
            await callback.message.answer(
                report,
                parse_mode="HTML",
                reply_markup=builder.as_markup()
            )
    await callback.answer()


@router.callback_query(F.data.in_({"stats_day", "stats_week"}))
async def stats_placeholder(callback: types.CallbackQuery) -> None:
    """Placeholder handler for future stats features."""
    await callback.answer("Скоро будет доступно!", show_alert=True)


@router.callback_query(F.data.startswith("stats_history"))
async def stats_history_handler(callback: types.CallbackQuery) -> None:
    """Show consumption logs with delete buttons for specific date."""
    parts = callback.data.split(":")
    
    # Check if date is provided
    target_date = datetime.utcnow().date()
    if len(parts) > 1:
        try:
            target_date = datetime.strptime(parts[1], "%Y-%m-%d").date()
        except ValueError:
            pass
            
    user_id = callback.from_user.id
    
    async for session in get_db():
        stmt = select(ConsumptionLog).where(
            ConsumptionLog.user_id == user_id,
            func.date(ConsumptionLog.date) == target_date
        ).order_by(ConsumptionLog.date.desc())
        logs = (await session.execute(stmt)).scalars().all()
    
    # Use timedelta to find prev/next day
    from datetime import timedelta # Ensure import if needed locally or relying on module level
    
    builder = InlineKeyboardBuilder()
    
    date_label = target_date.strftime('%d.%m.%Y')
    
    if not logs:
        text = f"📝 <b>История за {date_label}</b>\n\nПока нет записей."
    else:
        text = f"📝 <b>История за {date_label}</b>\n\n<i>Нажмите 🗑️ чтобы удалить:</i>\n"
        for log in logs:
            time_str = (log.date.hour + 3) % 24 # Crude TZ adjustment, should use proper TZ
            time_fmt = f"{time_str:02d}:{log.date.minute:02d}"
            cal = int(log.calories) if log.calories else 0
            # Pass date to delete handler so it returns to correct date
            builder.button(text=f"🗑️ {log.product_name[:20]}", callback_data=f"delete_log:{log.id}:{target_date}")
            text += f"\n🕐 {time_fmt} — {log.product_name} ({cal} ккал)"
        
        builder.adjust(1)
    
    builder.button(text="🔙 Назад", callback_data=f"menu_stats:{target_date}")
    
    try:
        await callback.message.edit_caption(caption=text, parse_mode="HTML", reply_markup=builder.as_markup())
    except Exception:
        try:
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
        except Exception:
            await callback.message.delete()
            await callback.message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("delete_log:"))
async def delete_log_handler(callback: types.CallbackQuery) -> None:
    """Delete a consumption log entry."""
    parts = callback.data.split(":")
    log_id = int(parts[1])
    
    # Logic to preserve date
    target_date_str = ""
    if len(parts) > 2:
        target_date_str = parts[2]
    
    async for session in get_db():
        log = await session.get(ConsumptionLog, log_id)
        if log and log.user_id == callback.from_user.id:
            await session.delete(log)
            await session.commit()
            await callback.answer("✅ Запись удалена!")
        else:
            await callback.answer("⚠️ Запись не найдена", show_alert=True)
            return
    
    # Refresh history with correct date
    if target_date_str:
        # Hack: overwrite callback data to trick handlers
        callback.data = f"stats_history:{target_date_str}"
        await stats_history_handler(callback)
    else:
        # Default today
        callback.data = "stats_history"
        await stats_history_handler(callback)

