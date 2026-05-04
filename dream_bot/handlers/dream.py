from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ChatAction
from aiogram.types import FSInputFile
from database.base import SessionLocal
from database.models import User, DreamLog
from services.ai_audio import process_dream_multimodal
from utils.audio_converter import convert_ogg_to_wav, convert_wav_to_ogg
import os
import logging

router = Router()


class DreamStates(StatesGroup):
    waiting_for_clarification = State()


async def _download_voice(message: types.Message) -> tuple[str | None, str | None]:
    """Скачивает голосовое сообщение, конвертирует OGG→WAV. Возвращает (ogg_path, wav_path)."""
    file_id = message.voice.file_id
    file = await message.bot.get_file(file_id)
    ogg_path = f"temp_in_{file_id}.ogg"
    wav_path = f"temp_in_{file_id}.wav"
    await message.bot.download_file(file.file_path, ogg_path)
    success = await convert_ogg_to_wav(ogg_path, wav_path)
    if not success:
        if os.path.exists(ogg_path):
            os.remove(ogg_path)
        return None, None
    return ogg_path, wav_path


async def _send_result(message: types.Message, interpretation: str, balance: int, wav_path: str | None):
    """Отправляет текст + голосовое сообщение пользователю."""
    if wav_path and os.path.exists(wav_path):
        final_ogg = f"response_final_{message.message_id}.ogg"
        success = await convert_wav_to_ogg(wav_path, final_ogg)
        if success and os.path.exists(final_ogg):
            await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.RECORD_VOICE)
            voice_file = FSInputFile(final_ogg)
            if len(interpretation) > 1000:
                await message.answer_voice(voice=voice_file, caption=f"✨ Осталось попыток: {balance}")
                await message.answer(f"✨ Толкование твоего сна:\n\n{interpretation}")
            else:
                await message.answer_voice(
                    voice=voice_file,
                    caption=f"✨ Толкование твоего сна:\n\n{interpretation}\n\nОсталось попыток: {balance}"
                )
            os.remove(final_ogg)
        else:
            await message.answer(f"✨ {interpretation}\n\nОсталось попыток: {balance}\n_(Голос Оракула сорвался)_")
        os.remove(wav_path)
    else:
        await message.answer(f"✨ Толкование твоего сна:\n\n{interpretation}\n\nОсталось попыток: {balance}")


async def _run_analysis(message: types.Message, dream_text: str | None, wav_input: str | None,
                        ogg_input: str | None, feeling: str, status_msg: types.Message):
    async with SessionLocal() as session:
        user = await session.get(User, message.from_user.id)
        if not user or user.dreams_balance <= 0:
            await status_msg.edit_text("🔮 <b>Твоя энергия иссякла.</b>\n\nКупи 'Звёздную пыль' (/buy) или пригласи друга.", parse_mode="HTML")
            return

        interpretation, output_wav, usage = await process_dream_multimodal(
            audio_path=wav_input,
            text_input=dream_text,
            feeling=feeling
        )

        prompt_tokens = usage.get("prompt_tokens", 0) if usage else 0
        completion_tokens = usage.get("completion_tokens", 0) if usage else 0
        cost_microusd = int(prompt_tokens * 0.6 + completion_tokens * 2.4)

        log = DreamLog(
            user_id=message.from_user.id,
            dream_text=dream_text or "[VOICE]",
            interpretation=interpretation,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost_microusd
        )
        session.add(log)
        user.dreams_balance -= 1
        balance = user.dreams_balance
        await session.commit()

    await status_msg.delete()
    await _send_result(message, interpretation, balance, output_wav)

    if ogg_input and os.path.exists(ogg_input):
        os.remove(ogg_input)
    if wav_input and os.path.exists(wav_input):
        os.remove(wav_input)


# ── Шаг 2: получаем уточнение и запускаем анализ ──────────────────────────────
@router.message(DreamStates.waiting_for_clarification, F.text | F.voice)
async def handle_clarification(message: types.Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()

    feeling = message.text if message.text else "не уточнено"
    status_msg = await message.answer("🔮 <i>Оракул погружается в глубины твоего сна...</i>", parse_mode="HTML")
    await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

    await _run_analysis(
        message=message,
        dream_text=data.get("dream_text"),
        wav_input=data.get("wav_input"),
        ogg_input=data.get("ogg_input"),
        feeling=feeling,
        status_msg=status_msg
    )


# ── Шаг 1: получаем сон, задаём уточняющий вопрос ─────────────────────────────
@router.message(F.text | F.voice)
async def handle_dream(message: types.Message, state: FSMContext):
    async with SessionLocal() as session:
        user = await session.get(User, message.from_user.id)
        if not user or user.dreams_balance <= 0:
            return await message.answer(
                "🔮 <b>Твоя энергия иссякла.</b>\n\nКупи 'Звёздную пыль' (/buy) или пригласи друга.",
                parse_mode="HTML"
            )

    dream_text = message.text
    ogg_input = None
    wav_input = None

    if message.voice:
        ogg_input, wav_input = await _download_voice(message)
        if not wav_input:
            return await message.answer("❌ Не удалось разобрать голосовое сообщение. Попробуй ещё раз.")
        dream_text = None

    await state.set_state(DreamStates.waiting_for_clarification)
    await state.update_data(dream_text=dream_text, wav_input=wav_input, ogg_input=ogg_input)

    await message.answer(
        "🌙 <i>Оракул внимает твоему сну...</i>\n\n"
        "<b>Одно уточнение:</b> какое чувство осталось после пробуждения? "
        "(тревога, радость, страх, спокойствие — любое слово)",
        parse_mode="HTML"
    )
