"""Тесты обработчика продуктового опроса (handlers/survey.py)."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from database.models import UserFeedback


def _make_callback(user_id: int, data: str):
    cb = MagicMock()
    cb.from_user = MagicMock(id=user_id)
    cb.data = data
    cb.answer = AsyncMock()
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock()
    cb.message.answer = AsyncMock()
    return cb


@pytest.mark.asyncio
async def test_sv1_answer_saves_correct_feedback_type(db_session, sample_user):
    """sv1:forgot → feedback_type='survey_v1', answer='sv1:forgot'."""
    from handlers.survey import handle_survey_answer

    cb = _make_callback(sample_user.id, "sv1:forgot")

    async def db_gen():
        yield db_session
    with patch("handlers.survey.get_db", return_value=db_gen()):
        await handle_survey_answer(cb)

    row = (await db_session.execute(
        select(UserFeedback).where(
            (UserFeedback.user_id == sample_user.id) &
            (UserFeedback.feedback_type == "survey_v1")
        )
    )).scalar_one()

    assert row.answer == "sv1:forgot"
    assert row.feedback_type == "survey_v1"
    cb.answer.assert_called_once()


@pytest.mark.asyncio
async def test_sv2_answer_saves_correct_feedback_type(db_session, sample_user):
    """sv2:no_result → feedback_type='survey_v2'."""
    from handlers.survey import handle_survey_answer

    cb = _make_callback(sample_user.id, "sv2:no_result")

    async def db_gen():
        yield db_session
    with patch("handlers.survey.get_db", return_value=db_gen()):
        await handle_survey_answer(cb)

    row = (await db_session.execute(
        select(UserFeedback).where(
            (UserFeedback.user_id == sample_user.id) &
            (UserFeedback.feedback_type == "survey_v2")
        )
    )).scalar_one()

    assert row.answer == "sv2:no_result"


@pytest.mark.asyncio
async def test_duplicate_click_not_saved_twice(db_session, sample_user):
    """Повторный клик по той же кнопке — вторая запись не создаётся."""
    from handlers.survey import handle_survey_answer

    cb = _make_callback(sample_user.id, "sv1:busy")

    async def db_gen():
        yield db_session

    with patch("handlers.survey.get_db", return_value=db_gen()):
        await handle_survey_answer(cb)

    # click again
    async def db_gen2():
        yield db_session
    with patch("handlers.survey.get_db", return_value=db_gen2()):
        await handle_survey_answer(cb)

    rows = (await db_session.execute(
        select(UserFeedback).where(
            (UserFeedback.user_id == sample_user.id) &
            (UserFeedback.feedback_type == "survey_v1")
        )
    )).scalars().all()

    assert len(rows) == 1, f"Ожидали 1 запись, получили {len(rows)}"


@pytest.mark.asyncio
async def test_thank_you_message_sent(db_session, sample_user):
    """После ответа пользователь получает благодарственное сообщение."""
    from handlers.survey import handle_survey_answer

    cb = _make_callback(sample_user.id, "sv1:too_hard")

    async def db_gen():
        yield db_session
    with patch("handlers.survey.get_db", return_value=db_gen()):
        await handle_survey_answer(cb)

    assert cb.message.edit_text.called or cb.message.answer.called, \
        "Пользователь должен получить ответное сообщение"
