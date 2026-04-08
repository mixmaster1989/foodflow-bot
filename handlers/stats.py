"""Module for statistics and consumption tracking handlers.

Contains:
- show_stats_menu: Display daily nutrition statistics
- stats_placeholder: Placeholder for future stats features
"""
import logging
from datetime import datetime, timedelta

from aiogram import Bot, F, Router, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, select

from database.base import get_db
from database.models import ConsumptionLog

logger = logging.getLogger(__name__)

router = Router()


@router.callback_query(F.data.startswith("menu_stats"))
async def show_stats_menu(callback: types.CallbackQuery) -> None:
    """Display daily nutrition statistics with date navigation."""
    parts = callback.data.split(":")

    # Check if date is provided
    target_date = datetime.now().date()
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
        if target_date == datetime.now().date():
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
    today = datetime.now().date()

    nav_row = []
    nav_row.append(types.InlineKeyboardButton(text="⬅️", callback_data=f"menu_stats:{prev_date}"))
    if target_date != today:
        nav_row.append(types.InlineKeyboardButton(text="Сегодня", callback_data=f"menu_stats:{today}"))
        nav_row.append(types.InlineKeyboardButton(text="➡️", callback_data=f"menu_stats:{next_date}"))

    builder.row(*nav_row)

    if logs:
        builder.button(text="📝 История", callback_data=f"stats_history:{target_date}")

    if target_date == today:
         builder.button(text="🗓️ Неделя", callback_data="stats_week")

    builder.button(text="🔙 Назад", callback_data="main_menu")
    builder.adjust(1)

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




@router.callback_query(F.data.in_({"stats_day", "stats_week"}))
async def stats_placeholder(callback: types.CallbackQuery) -> None:
    """Placeholder handler for future stats features."""
    await callback.answer("Скоро будет доступно!", show_alert=True)


from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

class EditLogStates(StatesGroup):
    """FSM states for editing consumption log."""
    waiting_for_field_value = State()


@router.callback_query(F.data.startswith("stats_history"))
async def stats_history_handler(callback: types.CallbackQuery) -> None:
    """Show consumption logs with edit/delete buttons for specific date."""
    parts = callback.data.split(":")

    # Check if date is provided
    target_date = datetime.now().date()
    if len(parts) > 1:
        try:
            target_date = datetime.strptime(parts[1], "%Y-%m-%d").date()
        except ValueError:
            pass

    user_id = callback.from_user.id
    logger.info(f"📝 User {user_id} requested history for {target_date}")

    from services.reports import generate_detailed_report
    text = await generate_detailed_report(user_id, target_date)

    if not text:
        text = f"📝 <b>История за {target_date.strftime('%d.%m.%Y')}</b>\n\nПока нет записей."

    async for session in get_db():
        stmt = select(ConsumptionLog).where(
            ConsumptionLog.user_id == user_id,
            func.date(ConsumptionLog.date) == target_date
        ).order_by(ConsumptionLog.date.desc())
        logs = (await session.execute(stmt)).scalars().all()

    builder = InlineKeyboardBuilder()

    if logs:
        text += "\n\n<i>Нажми ✏️ для правки или 🗑️ для удаления:</i>"
        for log in logs:
            cal = int(log.calories) if log.calories else 0
            time_str = log.date.strftime("%H:%M")
            # Edit button
            builder.button(
                text=f"✏️ {time_str} {log.product_name[:15]}", 
                callback_data=f"edit_log_show_fields:{log.id}:{target_date}"
            )
            # Delete button
            builder.button(
                text="🗑️", 
                callback_data=f"delete_log:{log.id}:{target_date}"
            )

        builder.adjust(2) # Pair edit and delete buttons

    builder.row(types.InlineKeyboardButton(text="🔙 Назад", callback_data=f"menu_stats:{target_date}"))

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


@router.callback_query(F.data.startswith("edit_log_show_fields:"))
async def edit_log_show_fields(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Show menu of fields to edit for a consumption log."""
    parts = callback.data.split(":")
    log_id = int(parts[1])
    target_date = parts[2]

    async for session in get_db():
        log = await session.get(ConsumptionLog, log_id)
        if not log or log.user_id != callback.from_user.id:
            await callback.answer("⚠️ Запись не найдена", show_alert=True)
            return

        builder = InlineKeyboardBuilder()
        builder.button(text="1. Название", callback_data=f"edit_log_field:{log_id}:product_name:{target_date}")
        builder.button(text="2. 🕒 Время", callback_data=f"edit_log_field:{log_id}:date:{target_date}")
        builder.button(text="3. 🔥 Калории", callback_data=f"edit_log_field:{log_id}:calories:{target_date}")
        builder.button(text="4. 🥩 Белки", callback_data=f"edit_log_field:{log_id}:protein:{target_date}")
        builder.button(text="5. 🥑 Жиры", callback_data=f"edit_log_field:{log_id}:fat:{target_date}")
        builder.button(text="6. 🍞 Углеводы", callback_data=f"edit_log_field:{log_id}:carbs:{target_date}")
        builder.button(text="7. 🥬 Клетчатка", callback_data=f"edit_log_field:{log_id}:fiber:{target_date}")
        
        builder.adjust(2)
        builder.row(types.InlineKeyboardButton(text="🔙 Назад", callback_data=f"stats_history:{target_date}"))

        text = (
            f"✏️ <b>Редактирование записи</b>\n\n"
            f"▫️ {log.product_name}\n"
            f"🕒 {log.date.strftime('%H:%M')}\n"
            f"🔥 {log.calories} ккал\n"
            f"📦 Б:{log.protein} Ж:{log.fat} У:{log.carbs} Кл:{log.fiber or 0}"
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


@router.callback_query(F.data.startswith("edit_log_field:"))
async def edit_log_select_field(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Start editing a specific field of a consumption log."""
    parts = callback.data.split(":")
    log_id = int(parts[1])
    field = parts[2]
    target_date = parts[3]

    field_names = {
        "product_name": "Название",
        "date": "Время (в формате ЧЧ:ММ)",
        "calories": "Калории",
        "protein": "Белки",
        "fat": "Жиры",
        "carbs": "Углеводы",
        "fiber": "Клетчатка"
    }

    await state.update_data(
        edit_log_id=log_id, 
        edit_field=field, 
        edit_target_date=target_date,
        edit_msg_id=callback.message.message_id # Store bot message ID to edit it later
    )
    await state.set_state(EditLogStates.waiting_for_field_value)

    await callback.message.answer(
        f"✍️ Введите новое значение для поля <b>{field_names.get(field, field)}</b>:",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(EditLogStates.waiting_for_field_value)
async def process_edit_log_value(message: types.Message, state: FSMContext, bot: Bot) -> None:
    """Process the new value for the edited field."""
    data = await state.get_data()
    log_id = data.get("edit_log_id")
    field = data.get("edit_field")
    target_date = data.get("edit_target_date")
    edit_msg_id = data.get("edit_msg_id")
    new_value = message.text.strip()

    async for session in get_db():
        log = await session.get(ConsumptionLog, log_id)
        if not log or log.user_id != message.from_user.id:
            await message.answer("❌ Запись не найдена.")
            await state.clear()
            return

        try:
            if field == "product_name":
                log.product_name = new_value
            elif field == "date":
                # Expect HH:MM
                try:
                    time_parts = new_value.split(":")
                    hour = int(time_parts[0])
                    minute = int(time_parts[1])
                    log.date = log.date.replace(hour=hour, minute=minute)
                except (ValueError, IndexError):
                    await message.answer("❌ Неверный формат времени. Введите ЧЧ:ММ (напр. 14:30)")
                    return
            elif field in ["calories", "protein", "fat", "carbs", "fiber"]:
                try:
                    log_val = float(new_value.replace(",", "."))
                    setattr(log, field, log_val)
                except ValueError:
                    await message.answer("❌ Введите число.")
                    return
            
            await session.commit()
            await message.answer(f"✅ Поле <b>{field}</b> обновлено!", parse_mode="HTML")
            
        except Exception as e:
            logger.error(f"Failed to update log {log_id}: {e}")
            await message.answer(f"❌ Ошибка обновления: {e}")

    await state.clear()
    
    # Return to history list using the STORED bot message ID
    # Re-trigger history handler with the correct message object
    try:
        msg_to_edit = await bot.edit_message_reply_markup(
            chat_id=message.chat.id,
            message_id=edit_msg_id,
            reply_markup=None # Temporary clear or keep
        )
        
        # Fake a callback to reuse the handler
        class FakeCallback:
            def __init__(self, message, user, data):
                self.message = message
                self.from_user = user
                self.data = data
            async def answer(self, *args, **kwargs): pass

        fake_cb = FakeCallback(msg_to_edit, message.from_user, f"stats_history:{target_date}")
        await stats_history_handler(fake_cb)
    except Exception as e:
        logger.error(f"Failed to return to history: {e}")
        await message.answer("✅ Запись обновлена! Используйте /stats чтобы увидеть изменения.")

