
from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.base import get_db
from database.models import User
from config import settings
from utils.user import get_user_display_name

router = Router()

class WardReplyStates(StatesGroup):
    composing_reply = State()

@router.callback_query(F.data.startswith("ward_reply:"))
async def ward_reply_start(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Start ward reply process."""
    parts = callback.data.split(":")
    curator_id = int(parts[1])
    
    await state.update_data(reply_curator_id=curator_id)
    await state.set_state(WardReplyStates.composing_reply)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="ward_cancel_reply")
    
    await callback.message.answer(
        "✏️ <b>Напишите ваш ответ куратору:</b>\n"
        "(Текст, фото или голосовое сообщение)",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@router.callback_query(F.data == "ward_cancel_reply")
async def ward_cancel_reply(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Cancel reply."""
    await state.clear()
    await callback.message.edit_text("❌ Ответ отменен.")
    await callback.answer()

@router.message(WardReplyStates.composing_reply)
async def ward_send_reply(message: types.Message, state: FSMContext) -> None:
    """Forward ward reply to curator."""
    data = await state.get_data()
    curator_id = data.get("reply_curator_id")
    
    if not curator_id:
        await state.clear()
        return

    # Get Ward Info
    async for session in get_db():
        ward = await session.get(User, message.from_user.id)
        ward_name = get_user_display_name(ward) if ward else "Подопечный"
        
    try:
        bot = Bot(token=settings.BOT_TOKEN)
        
        # Add Reply button for curator too (to keep cycle going if needed)
        reply_builder = InlineKeyboardBuilder()
        reply_builder.button(text="↩️ Ответить", callback_data=f"curator_nudge:{message.from_user.id}")

        content_type = message.content_type
        
        caption_prefix = f"📩 <b>Ответ от подопечного {ward_name}:</b>\n\n"
        
        if content_type == "text":
            await bot.send_message(
                curator_id,
                f"{caption_prefix}{message.text}",
                parse_mode="HTML",
                reply_markup=reply_builder.as_markup()
            )
        elif content_type == "photo":
            photo = message.photo[-1].file_id
            caption = f"{caption_prefix}{message.caption or ''}"
            await bot.send_photo(
                curator_id,
                photo=photo,
                caption=caption,
                parse_mode="HTML",
                reply_markup=reply_builder.as_markup()
            )
        elif content_type == "voice":
            voice = message.voice.file_id
            caption = f"{caption_prefix}🎤 Голосовое сообщение"
            await bot.send_voice(
                curator_id,
                voice=voice,
                caption=caption,
                parse_mode="HTML",
                reply_markup=reply_builder.as_markup()
            )
        else:
            await bot.send_message(
                curator_id,
                f"{caption_prefix}Unsupported content type: {content_type}",
                parse_mode="HTML",
                reply_markup=reply_builder.as_markup()
            )

        await bot.session.close()
        
        await message.answer("✅ Ответ отправлен!")
    except Exception as e:
        await message.answer(f"❌ Не удалось отправить ответ: {e}")
        
    await state.clear()
