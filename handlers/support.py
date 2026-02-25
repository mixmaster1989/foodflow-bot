import logging

from aiogram import Bot, F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import settings

router = Router()
logger = logging.getLogger(__name__)

class SupportStates(StatesGroup):
    waiting_for_message = State()

@router.callback_query(F.data == "menu_contact_dev")
async def contact_dev_start(callback: types.CallbackQuery, state: FSMContext):
    """Start contact developer flow."""
    await state.set_state(SupportStates.waiting_for_message)

    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="main_menu")

    await callback.message.edit_caption(
        caption=(
            "📩 <b>Написать разработчику</b>\n\n"
            "Опишите проблему или предложение одним сообщением.\n"
            "Я перешлю его напрямую администратору."
        ),
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@router.message(SupportStates.waiting_for_message)
async def process_support_message(message: types.Message, state: FSMContext, bot: Bot):
    """Forward user message to admins."""
    user_info = f"User: {message.from_user.full_name} (@{message.from_user.username}) [ID: {message.from_user.id}]"
    text = message.text or "[Not text message]"

    for admin_id in settings.ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"📩 <b>Новое обращение от пользователя:</b>\n{user_info}\n\n"
                f"📝 Текст:\n{text}",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Failed to send support msg to admin {admin_id}: {e}")

    await message.answer("✅ <b>Сообщение отправлено!</b> Разработчик ответит вам лично, если потребуется.", parse_mode="HTML")
    await state.clear()

    # Return to menu
    from handlers.menu import show_main_menu
    await show_main_menu(message, message.from_user.first_name, message.from_user.id)
