"""Обработчик ответов на продуктовый опрос (апрель 2026).

Сегмент 1 (sv1): зарегистрировались, прошли онбординг, ни разу не залогировали еду.
Сегмент 2 (sv2): залогировали хоть раз, потом исчезли.

Ответы хранятся в user_feedback с feedback_type='survey_v1'/'survey_v2'.
Никаких бонусов не выдаётся — чистый feedback-опрос.
"""
import logging

from aiogram import F, Router, types
from sqlalchemy import select

from database.base import get_db
from database.models import UserFeedback

router = Router()
logger = logging.getLogger(__name__)

SEGMENT_LABELS = {
    "sv1": "no_log",
    "sv2": "churned",
}

ANSWER_LABELS = {
    # sv1 — не залогировали
    "sv1:no_understand": "Не понял как пользоваться",
    "sv1:too_hard": "Лень / казалось сложно",
    "sv1:forgot": "Забыл",
    "sv1:no_value": "Не увидел смысла",
    "sv1:busy": "Занят, вернусь позже",
    # sv2 — залогировали и ушли
    "sv2:no_result": "Не увидел пользы/результата",
    "sv2:too_boring": "Скучно / рутинно",
    "sv2:too_hard": "Сложно, много усилий",
    "sv2:forgot": "Просто забыл",
    "sv2:other_app": "Нашёл другой способ",
}


@router.callback_query(F.data.startswith("sv1:") | F.data.startswith("sv2:"))
async def handle_survey_answer(callback: types.CallbackQuery) -> None:
    user_id = callback.from_user.id
    data = callback.data  # e.g. "sv1:forgot"

    segment = "sv1" if data.startswith("sv1:") else "sv2"
    feedback_type = f"survey_v{segment[2]}"  # survey_v1 / survey_v2

    answer_label = ANSWER_LABELS.get(data, data)

    async for session in get_db():
        # Prevent duplicate — only count first answer
        existing = (await session.execute(
            select(UserFeedback).where(
                (UserFeedback.user_id == user_id) &
                (UserFeedback.feedback_type == feedback_type)
            )
        )).scalar_one_or_none()

        if not existing:
            session.add(UserFeedback(
                user_id=user_id,
                feedback_type=feedback_type,
                answer=data,
            ))
            await session.commit()
            logger.info(f"[SURVEY] user={user_id} segment={segment} answer={data}")

        break

    await callback.answer()

    thank_you = (
        "💙 Спасибо, это очень ценно!\n\n"
        "Твой ответ поможет нам сделать бот понятнее. "
        "Если захочешь поделиться чем-то ещё — просто напиши."
    )

    try:
        await callback.message.edit_text(
            f"✅ <b>{answer_label}</b>\n\n{thank_you}",
            parse_mode="HTML",
        )
    except Exception:
        await callback.message.answer(thank_you)
