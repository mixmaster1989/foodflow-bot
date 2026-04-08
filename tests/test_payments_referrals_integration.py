from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from database.base import get_db
from database.models import Subscription, User
from handlers.payments import handle_check_yookassa_payment, successful_payment_handler


@pytest.mark.asyncio
async def test_yookassa_triggers_referral_service(monkeypatch, db_session, mock_callback_query):
    from services import referral_service

    user = User(id=9001, username="yookassa_user")
    db_session.add(user)
    await db_session.commit()

    # Подменяем get_db, чтобы payments использовал тестовую сессию
    async def _get_db_override():
        yield db_session

    monkeypatch.setattr("handlers.payments.get_db", _get_db_override)

    # Мокаем YooKassaService.check_payment_status
    payment_mock = SimpleNamespace(
        status="succeeded",
        metadata={"user_id": user.id, "tier": "pro", "months": 1},
        amount=SimpleNamespace(value="299", currency="RUB"),
    )

    async def _check_payment_status(payment_id: str):
        assert payment_id == "test_payment_id"
        return payment_mock

    monkeypatch.setattr(
        "handlers.payments.YooKassaService.check_payment_status",
        _check_payment_status,
    )

    # Мокаем ReferralService.handle_successful_payment
    called = {}

    async def _handle_successful_payment(user_id: int, tier: str):
        called["user_id"] = user_id
        called["tier"] = tier

    monkeypatch.setattr(
        referral_service.ReferralService,
        "handle_successful_payment",
        _handle_successful_payment,
    )

    mock_callback_query.data = "check_pay:test_payment_id"

    await handle_check_yookassa_payment(mock_callback_query)

    # Проверяем, что подписка обновлена
    sub = (await db_session.execute(select(Subscription).where(Subscription.user_id == user.id))).scalar_one()
    assert sub.tier == "pro"

    # И что ReferralService был вызван
    assert called["user_id"] == user.id
    assert called["tier"] == "pro"


@pytest.mark.asyncio
async def test_stars_triggers_referral_service(monkeypatch, db_session, mock_telegram_message):
    from services import referral_service

    user = User(id=9101, username="stars_user")
    db_session.add(user)
    await db_session.commit()

    # Подменяем get_db, чтобы payments использовал тестовую сессию
    async def _get_db_override():
        yield db_session

    monkeypatch.setattr("handlers.payments.get_db", _get_db_override)

    # Собираем успешный платёж
    payment = SimpleNamespace(
        invoice_payload=f"once_pro_1_{user.id}",
        total_amount=200,
        telegram_payment_charge_id="charge123",
    )

    mock_telegram_message.successful_payment = payment
    mock_telegram_message.from_user.id = user.id

    # Мокаем ReferralService.handle_successful_payment
    called = {}

    async def _handle_successful_payment(user_id: int, tier: str):
        called["user_id"] = user_id
        called["tier"] = tier

    monkeypatch.setattr(
        referral_service.ReferralService,
        "handle_successful_payment",
        _handle_successful_payment,
    )

    await successful_payment_handler(mock_telegram_message)

    # Проверяем, что подписка обновлена
    sub = (await db_session.execute(select(Subscription).where(Subscription.user_id == user.id))).scalar_one()
    assert sub.tier == "pro"

    # И что ReferralService был вызван
    assert called["user_id"] == user.id
    assert called["tier"] == "pro"

