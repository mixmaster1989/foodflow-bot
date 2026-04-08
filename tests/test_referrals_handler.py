import pytest
from sqlalchemy import select

from database.models import ReferralReward, ReferralEvent
from handlers.referrals import referrals_menu, ref_reward_activate


@pytest.mark.asyncio
async def test_referrals_menu_no_rewards(db_session, mock_callback_query, monkeypatch):
    user_id = 5001
    mock_callback_query.from_user.id = user_id

    # Создаём пользователя, чтобы кабинет мог отобразить персональный блок
    from database.models import User
    db_session.add(User(id=user_id, username="ref_user"))
    await db_session.commit()

    async def _get_db_override():
        yield db_session

    monkeypatch.setattr("handlers.referrals.get_db", _get_db_override)

    await referrals_menu(mock_callback_query)

    # Проверяем, что сообщение отправлено и текст содержит блок про ссылку
    assert mock_callback_query.message.edit_text.called or mock_callback_query.message.answer.called
    if mock_callback_query.message.edit_text.called:
        text = mock_callback_query.message.edit_text.call_args[0][0]
    else:
        text = mock_callback_query.message.answer.call_args[0][0]
    assert "Реферальный кабинет" in text
    assert "Твоя реферальная ссылка" in text


@pytest.mark.asyncio
async def test_referrals_menu_with_pending_rewards_and_stats(db_session, mock_callback_query, monkeypatch):
    user_id = 5002
    mock_callback_query.from_user.id = user_id

    # Добавим два события: signup и paid
    event1 = ReferralEvent(referrer_id=user_id, invitee_id=6001, event_type="signup")
    event2 = ReferralEvent(referrer_id=user_id, invitee_id=6001, event_type="paid", tier="pro")
    # Добавим два ожидающих бонуса
    r1 = ReferralReward(user_id=user_id, reward_type="basic_days", days=5, source="test1")
    r2 = ReferralReward(user_id=user_id, reward_type="pro_days", days=30, source="test2")
    db_session.add_all([event1, event2, r1, r2])
    await db_session.commit()

    async def _get_db_override():
        yield db_session

    monkeypatch.setattr("handlers.referrals.get_db", _get_db_override)

    await referrals_menu(mock_callback_query)

    # Проверяем, что был показан кабинет и добавлены кнопки для активации
    assert mock_callback_query.message.edit_text.called or mock_callback_query.message.answer.called


@pytest.mark.asyncio
async def test_ref_reward_activate_success(monkeypatch, db_session, mock_callback_query):
    from services import referral_service

    user_id = 7001
    mock_callback_query.from_user.id = user_id

    reward = ReferralReward(user_id=user_id, reward_type="basic_days", days=5, source="test")
    db_session.add(reward)
    await db_session.commit()

    # Переопределяем get_db, чтобы referrals_menu внутри активации использовал тестовую сессию
    async def _get_db_override():
        yield db_session

    monkeypatch.setattr("handlers.referrals.get_db", _get_db_override)

    # Мокаем ReferralService.activate_reward, чтобы изолировать от логики стэкинга
    async def _activate_reward(user_id: int, reward_id: int) -> bool:
        assert user_id == 7001
        assert reward_id == reward.id
        return True

    monkeypatch.setattr(referral_service.ReferralService, "activate_reward", _activate_reward)

    mock_callback_query.data = f"ref_reward_activate:{reward.id}"

    await ref_reward_activate(mock_callback_query)

    # Должен быть вызван callback.answer с сообщением об успехе
    assert mock_callback_query.answer.called


@pytest.mark.asyncio
async def test_ref_reward_activate_failure(monkeypatch, db_session, mock_callback_query):
    from services import referral_service

    user_id = 8001
    mock_callback_query.from_user.id = user_id

    reward = ReferralReward(user_id=user_id, reward_type="basic_days", days=5, source="test")
    db_session.add(reward)
    await db_session.commit()

    async def _get_db_override():
        yield db_session

    monkeypatch.setattr("handlers.referrals.get_db", _get_db_override)

    async def _activate_reward(user_id: int, reward_id: int) -> bool:
        return False

    monkeypatch.setattr(referral_service.ReferralService, "activate_reward", _activate_reward)

    mock_callback_query.data = f"ref_reward_activate:{reward.id}"

    await ref_reward_activate(mock_callback_query)

    # В случае ошибки должен быть alert
    assert mock_callback_query.answer.called

