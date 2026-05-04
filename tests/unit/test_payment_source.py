"""Тесты для колонки Subscription.payment_source.

Покрывают все callsite, которые проставляют source, плюс инварианты:
- реальные платежи (Stars/YooKassa) перетирают любой source
- бесплатные источники (referral/feedback) НЕ перетирают реальный платёж
"""
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from database.models import (
    PAID_SOURCES,
    PAYMENT_SOURCE_FEEDBACK,
    PAYMENT_SOURCE_REFERRAL,
    PAYMENT_SOURCE_STARS,
    PAYMENT_SOURCE_TRIAL,
    PAYMENT_SOURCE_YOOKASSA,
    ReferralReward,
    Subscription,
    User,
)


# ============================================================
# Helpers
# ============================================================

def _patch_get_db(module_path: str, db_session):
    """Возвращает context manager, патчащий get_db в указанном модуле."""
    async def db_gen():
        yield db_session
    return patch(module_path, return_value=db_gen())


# ============================================================
# 1. Онбординг (handlers/onboarding.py:511) — trial
# ============================================================

@pytest.mark.asyncio
async def test_onboarding_creates_trial_source(
    db_session, mock_callback_query, mock_fsm_context, sample_user
):
    """finish_onboarding создаёт подписку с payment_source='trial'."""
    from handlers.onboarding import handle_goal_accept

    mock_callback_query.message.chat.id = sample_user.id
    mock_callback_query.message.chat.first_name = "Тест"
    mock_fsm_context.get_data = AsyncMock(return_value={
        "gender": "male", "age": 30, "height": 180, "weight": 80.0,
        "goal": "lose_weight",
        "pending_targets": {"calories": 2000, "protein": 150, "fat": 60, "carbs": 200},
    })

    with _patch_get_db("handlers.onboarding.get_db", db_session):
        await handle_goal_accept(mock_callback_query, mock_fsm_context)

    sub = (await db_session.execute(
        select(Subscription).where(Subscription.user_id == sample_user.id)
    )).scalar_one()
    assert sub.tier == "pro"
    assert sub.payment_source == PAYMENT_SOURCE_TRIAL
    assert sub.yookassa_payment_id is None


# ============================================================
# 2-3. Feedback poll (handlers/feedback.py)
# ============================================================

@pytest.mark.asyncio
async def test_feedback_creates_feedback_bonus_source(db_session, sample_user):
    """Опрос → новая подписка с payment_source='feedback_bonus'."""
    from handlers.feedback import process_feedback_poll

    callback = MagicMock()
    callback.from_user = MagicMock(id=sample_user.id)
    callback.data = "poll_fb:still_using"
    callback.answer = AsyncMock()
    callback.message = MagicMock()
    callback.message.edit_text = AsyncMock()
    callback.message.answer = AsyncMock()

    with _patch_get_db("handlers.feedback.get_db", db_session):
        await process_feedback_poll(callback)

    sub = (await db_session.execute(
        select(Subscription).where(Subscription.user_id == sample_user.id)
    )).scalar_one()
    assert sub.payment_source == PAYMENT_SOURCE_FEEDBACK
    assert sub.tier == "pro"


@pytest.mark.asyncio
async def test_feedback_extend_does_not_overwrite_stars(db_session, sample_user):
    """Опрос НЕ перетирает payment_source='stars' (защита PAID_SOURCES)."""
    from handlers.feedback import process_feedback_poll

    # Pre-create paid Stars subscription
    sub = Subscription(
        user_id=sample_user.id,
        tier="pro",
        starts_at=datetime.now(),
        expires_at=datetime.now() + timedelta(days=30),
        is_active=True,
        payment_source=PAYMENT_SOURCE_STARS,
        telegram_payment_charge_id="charge_abc123",
    )
    db_session.add(sub)
    await db_session.commit()

    callback = MagicMock()
    callback.from_user = MagicMock(id=sample_user.id)
    callback.data = "poll_fb:still_using"
    callback.answer = AsyncMock()
    callback.message = MagicMock()
    callback.message.edit_text = AsyncMock()
    callback.message.answer = AsyncMock()

    with _patch_get_db("handlers.feedback.get_db", db_session):
        await process_feedback_poll(callback)

    await db_session.refresh(sub)
    assert sub.payment_source == PAYMENT_SOURCE_STARS, \
        "Stars-источник должен сохраниться — feedback это freebie"
    assert sub.telegram_payment_charge_id == "charge_abc123"


# ============================================================
# 4. YooKassa (handlers/payments.py:455-479)
# ============================================================

@pytest.mark.asyncio
async def test_yookassa_success_sets_yookassa_source_and_payment_id(db_session, sample_user):
    """Успешный YooKassa-платёж проставляет source='yookassa' + yookassa_payment_id."""
    from handlers.payments import handle_check_yookassa_payment

    payment_id = "yk_payment_xyz789"

    fake_payment = MagicMock()
    fake_payment.status = "succeeded"
    fake_payment.metadata = {"user_id": str(sample_user.id), "tier": "pro", "months": "1"}
    fake_payment.amount = MagicMock(value="299.00", currency="RUB")

    callback = MagicMock()
    callback.data = f"check_pay:{payment_id}"
    callback.answer = AsyncMock()
    callback.message = MagicMock()
    callback.message.edit_text = AsyncMock()

    with _patch_get_db("handlers.payments.get_db", db_session), \
         patch("handlers.payments.YooKassaService.check_payment_status",
               new=AsyncMock(return_value=fake_payment)), \
         patch("handlers.payments.ReferralService.handle_successful_payment",
               new=AsyncMock(return_value=None)):
        await handle_check_yookassa_payment(callback)

    sub = (await db_session.execute(
        select(Subscription).where(Subscription.user_id == sample_user.id)
    )).scalar_one()
    assert sub.payment_source == PAYMENT_SOURCE_YOOKASSA
    assert sub.yookassa_payment_id == payment_id
    assert sub.tier == "pro"


@pytest.mark.asyncio
async def test_yookassa_overrides_trial(db_session, sample_user):
    """YooKassa-платёж перетирает payment_source='trial'."""
    from handlers.payments import handle_check_yookassa_payment

    # Pre-create trial sub
    db_session.add(Subscription(
        user_id=sample_user.id, tier="pro",
        starts_at=datetime.now() - timedelta(days=2),
        expires_at=datetime.now() + timedelta(days=1),
        is_active=True, payment_source=PAYMENT_SOURCE_TRIAL,
    ))
    await db_session.commit()

    payment_id = "yk_overrides_trial"
    fake_payment = MagicMock()
    fake_payment.status = "succeeded"
    fake_payment.metadata = {"user_id": str(sample_user.id), "tier": "pro", "months": "1"}
    fake_payment.amount = MagicMock(value="299.00", currency="RUB")

    callback = MagicMock()
    callback.data = f"check_pay:{payment_id}"
    callback.answer = AsyncMock()
    callback.message = MagicMock()
    callback.message.edit_text = AsyncMock()

    with _patch_get_db("handlers.payments.get_db", db_session), \
         patch("handlers.payments.YooKassaService.check_payment_status",
               new=AsyncMock(return_value=fake_payment)), \
         patch("handlers.payments.ReferralService.handle_successful_payment",
               new=AsyncMock(return_value=None)):
        await handle_check_yookassa_payment(callback)

    sub = (await db_session.execute(
        select(Subscription).where(Subscription.user_id == sample_user.id)
    )).scalar_one()
    assert sub.payment_source == PAYMENT_SOURCE_YOOKASSA
    assert sub.yookassa_payment_id == payment_id


# ============================================================
# 5-6. Telegram Stars (handlers/payments.py:600-623)
# ============================================================

def _make_stars_message(user_id: int, payload: str, charge_id: str = "stars_charge_xyz"):
    msg = MagicMock()
    msg.from_user = MagicMock(id=user_id)
    payment = MagicMock()
    payment.invoice_payload = payload
    payment.telegram_payment_charge_id = charge_id
    payment.total_amount = 200
    payment.currency = "XTR"
    msg.successful_payment = payment
    msg.answer = AsyncMock()
    msg.reply = AsyncMock()
    return msg


@pytest.mark.asyncio
async def test_stars_subscription_sets_stars_source(db_session, sample_user):
    """sub_pro_<uid>: payment_source='stars', charge_id сохранён."""
    from handlers.payments import successful_payment_handler

    msg = _make_stars_message(sample_user.id, f"sub_pro_{sample_user.id}", "ch_AAA")

    with _patch_get_db("handlers.payments.get_db", db_session), \
         patch("handlers.payments.ReferralService.handle_successful_payment",
               new=AsyncMock(return_value=None)):
        await successful_payment_handler(msg)

    sub = (await db_session.execute(
        select(Subscription).where(Subscription.user_id == sample_user.id)
    )).scalar_one()
    assert sub.payment_source == PAYMENT_SOURCE_STARS
    assert sub.tier == "pro"
    assert sub.telegram_payment_charge_id == "ch_AAA"
    assert sub.auto_renew is True


@pytest.mark.asyncio
async def test_stars_once_sets_stars_source_charge_id_none(db_session, sample_user):
    """once_basic_3_<uid>: payment_source='stars' + charge_id=None (no auto-renew)."""
    from handlers.payments import successful_payment_handler

    msg = _make_stars_message(sample_user.id, f"once_basic_3_{sample_user.id}", "ch_BBB")

    with _patch_get_db("handlers.payments.get_db", db_session), \
         patch("handlers.payments.ReferralService.handle_successful_payment",
               new=AsyncMock(return_value=None)):
        await successful_payment_handler(msg)

    sub = (await db_session.execute(
        select(Subscription).where(Subscription.user_id == sample_user.id)
    )).scalar_one()
    assert sub.payment_source == PAYMENT_SOURCE_STARS
    assert sub.tier == "basic"
    assert sub.telegram_payment_charge_id is None, \
        "once-платежи хранятся без charge_id (нет автопродления)"
    assert sub.auto_renew is False


@pytest.mark.asyncio
async def test_trial_to_stars_upgrade_overwrites_source(db_session, sample_user):
    """Stars-платёж перетирает payment_source='trial' (real payment wins)."""
    from handlers.payments import successful_payment_handler

    db_session.add(Subscription(
        user_id=sample_user.id, tier="pro",
        starts_at=datetime.now() - timedelta(days=2),
        expires_at=datetime.now() + timedelta(days=1),
        is_active=True, payment_source=PAYMENT_SOURCE_TRIAL,
    ))
    await db_session.commit()

    msg = _make_stars_message(sample_user.id, f"sub_pro_{sample_user.id}", "ch_OVERRIDE")

    with _patch_get_db("handlers.payments.get_db", db_session), \
         patch("handlers.payments.ReferralService.handle_successful_payment",
               new=AsyncMock(return_value=None)):
        await successful_payment_handler(msg)

    sub = (await db_session.execute(
        select(Subscription).where(Subscription.user_id == sample_user.id)
    )).scalar_one()
    assert sub.payment_source == PAYMENT_SOURCE_STARS
    assert sub.telegram_payment_charge_id == "ch_OVERRIDE"


# ============================================================
# 7. Web-регистрация (api/routers/auth.py:276)
# ============================================================

@pytest.mark.asyncio
async def test_web_registration_sets_trial_source(db_session):
    """POST /api/auth/web-register создаёт sub с payment_source='trial'."""
    from httpx import ASGITransport, AsyncClient

    from api.main import app
    from database.base import get_db

    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/api/auth/web-register", json={
                "email": "trialcheck@example.com",
                "password": "testpassword123",
                "name": "Trial Web",
            })
        assert resp.status_code == 200, resp.text
    finally:
        app.dependency_overrides.clear()

    user = (await db_session.execute(
        select(User).where(User.email == "trialcheck@example.com")
    )).scalar_one()
    sub = (await db_session.execute(
        select(Subscription).where(Subscription.user_id == user.id)
    )).scalar_one()
    assert sub.payment_source == PAYMENT_SOURCE_TRIAL
    assert sub.tier == "pro"


# ============================================================
# 8-9. Referral service (services/referral_service.py)
# ============================================================

@pytest.mark.asyncio
async def test_referral_activate_sets_referral_when_no_sub(db_session, sample_user):
    """activate_reward без существующей подписки → создаёт с source='referral'."""
    from services.referral_service import ReferralService

    reward = ReferralReward(
        user_id=sample_user.id,
        reward_type="pro_days",
        days=14,
        source="ref_invite_paid",
        is_active=False,
    )
    db_session.add(reward)
    await db_session.commit()
    await db_session.refresh(reward)

    with _patch_get_db("services.referral_service.get_db", db_session):
        ok = await ReferralService.activate_reward(sample_user.id, reward.id)

    assert ok is True
    sub = (await db_session.execute(
        select(Subscription).where(Subscription.user_id == sample_user.id)
    )).scalar_one()
    assert sub.payment_source == PAYMENT_SOURCE_REFERRAL
    assert sub.tier == "pro"


@pytest.mark.asyncio
async def test_referral_does_not_overwrite_stars(db_session, sample_user):
    """activate_reward НЕ перетирает payment_source='stars' (защита PAID_SOURCES)."""
    from services.referral_service import ReferralService

    db_session.add(Subscription(
        user_id=sample_user.id, tier="pro",
        starts_at=datetime.now(),
        expires_at=datetime.now() + timedelta(days=30),
        is_active=True,
        payment_source=PAYMENT_SOURCE_STARS,
        telegram_payment_charge_id="ch_paid_keep",
    ))
    reward = ReferralReward(
        user_id=sample_user.id, reward_type="pro_days",
        days=14, source="ref_invite_paid", is_active=False,
    )
    db_session.add(reward)
    await db_session.commit()
    await db_session.refresh(reward)

    with _patch_get_db("services.referral_service.get_db", db_session):
        ok = await ReferralService.activate_reward(sample_user.id, reward.id)

    assert ok is True
    sub = (await db_session.execute(
        select(Subscription).where(Subscription.user_id == sample_user.id)
    )).scalar_one()
    assert sub.payment_source == PAYMENT_SOURCE_STARS, \
        "Stars-источник должен сохраниться — реферал это freebie"
    assert sub.telegram_payment_charge_id == "ch_paid_keep"


# ============================================================
# Sanity check — PAID_SOURCES константа
# ============================================================

def test_paid_sources_contains_real_payments_only():
    """PAID_SOURCES — только источники реальной оплаты."""
    assert PAYMENT_SOURCE_STARS in PAID_SOURCES
    assert PAYMENT_SOURCE_YOOKASSA in PAID_SOURCES
    # Триалы и бонусы — НЕ в PAID_SOURCES
    assert PAYMENT_SOURCE_TRIAL not in PAID_SOURCES
    assert PAYMENT_SOURCE_FEEDBACK not in PAID_SOURCES
    assert PAYMENT_SOURCE_REFERRAL not in PAID_SOURCES
