import logging
import subprocess
from datetime import datetime

from aiogram import Bot, F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from config import settings
from database.base import get_db
from database.models import User
from handlers.base import BaseCommandHandler
from monitoring import get_system_health
from services.reports import generate_admin_daily_digest, generate_admin_stats_csv
from aiogram.types import BufferedInputFile

router = Router()
logger = logging.getLogger(__name__)


class AdminStates(StatesGroup):
    selecting_user = State()
    typing_message = State()


def is_admin(user_id: int) -> bool:
    return user_id in settings.ADMIN_IDS


@router.message(Command("send_test"))
async def send_test_message(message: types.Message):
    """
    Send a test message to a user.
    Usage: /send_test <user_id> <message>
    """
    if not is_admin(message.from_user.id):
        return

    args = message.text.split()
    if len(args) < 3:
        await message.reply("Usage: /send_test <user_id> <message>")
        return

    user_id_str, message_text = args[1], " ".join(args[2:])

    if not user_id_str.isdigit():
        await message.reply("Invalid user ID.")
        return

    user_id = int(user_id_str)

    try:
        await BaseCommandHandler.send_arbitrary_message(user_id, message_text)
        await message.reply("Message sent successfully.")
    except Exception as e:
        await message.reply(f"Error sending message: {e}")


@router.callback_query(F.data == "admin_restart_bot")
async def restart_bot_handler(callback: types.CallbackQuery):
    """Restart the bot process via PM2 (Admin only)."""
    user_id = callback.from_user.id
    if user_id not in settings.ADMIN_IDS:
        await callback.answer("⛔ Access Denied", show_alert=True)
        return

    await callback.message.answer("🔄 <b>Перезагрузка бота...</b>\n\nЭто займет пару секунд.", parse_mode="HTML")
    await callback.answer()

    logger.warning(f"Admin {user_id} initiated bot restart.")

    try:
        subprocess.Popen(["pm2", "restart", "foodflow-bot"])
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка при перезапуске: {e}")


@router.callback_query(F.data == "admin_send_message")
async def admin_send_message_start(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Show user list for admin to select recipient."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    async for session in get_db():
        users = (await session.execute(select(User))).scalars().all()

        builder = InlineKeyboardBuilder()
        for user in users:
            name = user.username or f"ID:{user.id}"
            builder.button(text=f"👤 {name}", callback_data=f"admin_select_user:{user.id}")
        builder.button(text="❌ Отмена", callback_data="main_menu")
        builder.adjust(1)

        try:
            await callback.message.edit_text(
                "📨 <b>Выберите получателя:</b>",
                parse_mode="HTML",
                reply_markup=builder.as_markup()
            )
        except Exception:
            await callback.message.delete()
            await callback.message.answer(
                "📨 <b>Выберите получателя:</b>",
                parse_mode="HTML",
                reply_markup=builder.as_markup()
            )
        await state.set_state(AdminStates.selecting_user)
    await callback.answer()


@router.callback_query(AdminStates.selecting_user, F.data.startswith("admin_select_user:"))
async def admin_select_user(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Handle user selection, ask for message."""
    if not is_admin(callback.from_user.id):
        return

    user_id = int(callback.data.split(":")[1])

    async for session in get_db():
        user = await session.get(User, user_id)
        user_name = user.username if user else f"ID:{user_id}"

    await state.update_data(target_user_id=user_id, target_user_name=user_name)
    await state.set_state(AdminStates.typing_message)

    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="admin_cancel")

    await callback.message.edit_text(
        f"📝 Напишите сообщение для <b>{user_name}</b>:\n\n"
        "<i>Просто отправьте текст в чат</i>",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.message(AdminStates.typing_message)
async def admin_send_message(message: types.Message, state: FSMContext, bot: Bot) -> None:
    """Send the typed message to selected user."""
    if not is_admin(message.from_user.id):
        return

    data = await state.get_data()
    target_user_id = data.get("target_user_id")
    target_user_name = data.get("target_user_name")

    if not target_user_id:
        await message.answer("⚠️ Получатель не выбран")
        await state.clear()
        return

    try:
        await bot.send_message(
            chat_id=target_user_id,
            text=f"💬 <b>Сообщение от поддержки:</b>\n\n{message.text}",
            parse_mode="HTML"
        )
        await message.answer(
            f"✅ Сообщение отправлено пользователю <b>{target_user_name}</b>!",
            parse_mode="HTML"
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка отправки: {e}")

    await state.clear()


@router.callback_query(F.data == "admin_cancel")
async def admin_cancel(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Cancel admin action."""
    await state.clear()
    await callback.message.edit_text("❌ Отменено")
    await callback.answer()


@router.callback_query(F.data == "admin_view_stars")
async def admin_view_stars_handler(callback: types.CallbackQuery, bot: Bot):
    """Fetch and display total bot Star balance."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    try:
        # Use the NEW Bot API method available in Aiogram 3.22+
        # get_my_star_balance returns a StarAmount object with 'amount' field
        balance = await bot.get_my_star_balance()
        
        await callback.message.answer(
            f"💰 <b>Баланс Telegram Stars</b>\n\n"
            f"На счету бота: <b>{balance.amount} ⭐</b>\n\n"
            f"<i>Вывести можно через @BotFather -> Payments.</i>",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Failed to get Stars balance: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)
    
    await callback.answer()


@router.callback_query(F.data == "admin_healthcheck")
async def admin_healthcheck_handler(callback: types.CallbackQuery):
    """Show system health status (Admin only)."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    await callback.answer()

    try:
        h = await get_system_health()
        sys = h["system"]
        bot = h["bot"]

        procs_text = ""
        for p in h["python_processes"]:
            procs_text += f"  PID {p['pid']}: {p['memory_mb']:.0f}MB / {p['cpu_percent']:.1f}% CPU\n"

        text = (
            f"{h['health_status']} <b>FoodFlow Health</b>\n"
            f"<code>{h['timestamp'][:19]}</code>\n\n"
            f"<b>Система:</b>\n"
            f"  CPU: <b>{sys['cpu_percent']:.1f}%</b>\n"
            f"  RAM: <b>{sys['memory_used_gb']:.1f}</b>/{sys['memory_total_gb']:.1f}GB "
            f"({sys['memory_percent']:.0f}%)\n"
            f"  Диск: <b>{sys['disk_used_gb']:.1f}</b>/{sys['disk_total_gb']:.1f}GB "
            f"({sys['disk_percent']:.0f}%)\n\n"
            f"<b>Бот (с момента запуска):</b>\n"
            f"  Запросов: <b>{bot['total_requests']}</b> "
            f"({bot['requests_per_minute']:.1f}/мин)\n"
            f"  AI вызовов: <b>{bot['ai_calls']}</b> "
            f"(avg {bot['ai_avg_response_ms']}ms)\n"
            f"  Ошибок: <b>{bot['errors']}</b>\n\n"
            f"<b>Python процессы:</b>\n{procs_text}"
        )

        await callback.message.answer(text, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Healthcheck failed: {e}")
        await callback.message.answer(f"❌ Ошибка healthcheck: {e}")


@router.message(Command("admin_stats"))
async def admin_stats_command(message: types.Message):
    """Manually trigger and send admin daily digest with export button."""
    if not is_admin(message.from_user.id):
        return

    try:
        digest_text = await generate_admin_daily_digest()
        
        builder = InlineKeyboardBuilder()
        builder.button(text="📊 Скачать CSV (30 дней)", callback_data="admin_export_csv")
        
        await message.answer(digest_text, parse_mode="HTML", reply_markup=builder.as_markup())
    except Exception as e:
        logger.error(f"Error in /admin_stats: {e}")
        await message.answer(f"❌ Ошибка при генерации сводки: {e}")

@router.callback_query(F.data == "admin_export_csv")
@router.message(Command("admin_export"))
async def admin_export_handler(event: types.Message | types.CallbackQuery, bot: Bot):
    """Generate and send CSV statistics file."""
    user_id = event.from_user.id
    if not is_admin(user_id):
        if isinstance(event, types.CallbackQuery):
            await event.answer("⛔ Нет доступа", show_alert=True)
        return

    msg = event.message if isinstance(event, types.CallbackQuery) else event
    status_msg = await msg.answer("⏳ Генерирую файл статистики за 30 дней...")

    try:
        csv_io = await generate_admin_stats_csv(days=30)
        document = BufferedInputFile(csv_io.getvalue(), filename=f"stats_export_{datetime.now().strftime('%Y%m%d')}.csv")
        
        await bot.send_document(
            chat_id=user_id,
            document=document,
            caption="📊 <b>Экспорт статистики за последние 30 дней</b>\n\nФайл готов для загрузки в Excel или Google Таблицы.",
            parse_mode="HTML"
        )
        await status_msg.delete()
    except Exception as e:
        logger.error(f"Export failed: {e}")
        await status_msg.edit_text(f"❌ Ошибка при экспорте: {e}")

    if isinstance(event, types.CallbackQuery):
        await event.answer()
