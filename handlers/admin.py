import logging
import subprocess

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
