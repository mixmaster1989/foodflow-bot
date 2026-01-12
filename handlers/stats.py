"""Module for statistics and consumption tracking handlers.

Contains:
- show_stats_menu: Display daily nutrition statistics
- stats_placeholder: Placeholder for future stats features
"""
from datetime import date, datetime

from aiogram import F, Router, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, select

from database.base import get_db
from database.models import ConsumptionLog

router = Router()


@router.callback_query(F.data == "menu_stats")
async def show_stats_menu(callback: types.CallbackQuery) -> None:
    """Display daily nutrition statistics.

    Calculates and shows total calories, proteins, fats, carbs,
    and number of meals consumed today.

    Args:
        callback: Telegram callback query

    Returns:
        None

    """
    user_id: int = callback.from_user.id
    today: date = datetime.utcnow().date()

    async for session in get_db():
        # Get today's consumption
        stmt = select(ConsumptionLog).where(
            ConsumptionLog.user_id == user_id,
            func.date(ConsumptionLog.date) == today
        )
        logs = (await session.execute(stmt)).scalars().all()

        # Calculate totals
        total_calories = sum(log.calories for log in logs) if logs else 0
        total_protein = sum(log.protein for log in logs) if logs else 0
        total_fat = sum(log.fat for log in logs) if logs else 0
        total_carbs = sum(log.carbs for log in logs) if logs else 0

        # Build response
        if not logs:
            response = (
                "📊 <b>Статистика за сегодня</b>\n\n"
                "Пока нет данных.\n"
                "<i>Нажми 🍽️ на продукты в холодильнике, чтобы отметить что съел!</i>"
            )
        else:
            response = (
                f"📊 <b>Твоя статистика за сегодня</b>\n\n"
                f"🔥 Калории: <b>{total_calories:.0f}</b> ккал\n"
                f"🥩 Белки: <b>{total_protein:.1f}</b>г\n"
                f"🥑 Жиры: <b>{total_fat:.1f}</b>г\n"
                f"🍞 Углеводы: <b>{total_carbs:.1f}</b>г\n\n"
                f"📝 Приёмов пищи: <b>{len(logs)}</b>\n"
            )

    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Подробно", callback_data="stats_detailed")
    builder.button(text="📝 История", callback_data="stats_history")
    builder.button(text="📅 День", callback_data="stats_day")
    builder.button(text="🗓️ Неделя", callback_data="stats_week")
    builder.button(text="🔙 Назад", callback_data="main_menu")
    builder.adjust(2, 2, 1)

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


@router.callback_query(F.data == "stats_history")
async def stats_history_handler(callback: types.CallbackQuery) -> None:
    """Show today's consumption logs with delete buttons."""
    user_id = callback.from_user.id
    today = datetime.utcnow().date()
    
    async for session in get_db():
        stmt = select(ConsumptionLog).where(
            ConsumptionLog.user_id == user_id,
            func.date(ConsumptionLog.date) == today
        ).order_by(ConsumptionLog.date.desc())
        logs = (await session.execute(stmt)).scalars().all()
    
    builder = InlineKeyboardBuilder()
    
    if not logs:
        text = "📝 <b>История за сегодня</b>\n\nПока нет записей."
    else:
        lines = ["📝 <b>История за сегодня</b>\n\n<i>Нажмите 🗑️ чтобы удалить:</i>\n"]
        for log in logs:
            time_str = (log.date.hour + 3) % 24
            time_fmt = f"{time_str:02d}:{log.date.minute:02d}"
            cal = int(log.calories) if log.calories else 0
            lines.append(f"🕐 {time_fmt} — {log.product_name} ({cal} ккал)")
            builder.button(text=f"🗑️ {log.product_name[:20]}", callback_data=f"delete_log:{log.id}")
        text = "\n".join(lines)
        builder.adjust(1)
    
    builder.button(text="🔙 Назад", callback_data="menu_stats")
    
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
    log_id = int(callback.data.split(":")[1])
    
    async for session in get_db():
        log = await session.get(ConsumptionLog, log_id)
        if log and log.user_id == callback.from_user.id:
            await session.delete(log)
            await session.commit()
            await callback.answer("✅ Запись удалена!")
        else:
            await callback.answer("⚠️ Запись не найдена", show_alert=True)
            return
    
    # Refresh history
    await stats_history_handler(callback)

