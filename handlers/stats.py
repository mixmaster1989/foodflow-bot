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
    builder.button(text="📅 День", callback_data="stats_day") # Placeholder
    builder.button(text="🗓️ Неделя", callback_data="stats_week") # Placeholder
    builder.button(text="🔙 Назад", callback_data="main_menu")
    builder.adjust(2, 1)

    # Image path
    photo_path = types.FSInputFile("FoodFlow/assets/stats.png")

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

@router.callback_query(F.data.in_({"stats_day", "stats_week"}))
async def stats_placeholder(callback: types.CallbackQuery) -> None:
    """Placeholder handler for future stats features.

    Args:
        callback: Telegram callback query

    Returns:
        None

    """
    await callback.answer("Скоро будет доступно!", show_alert=True)

