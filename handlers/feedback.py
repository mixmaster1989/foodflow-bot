import logging
from datetime import datetime, timedelta

from aiogram import F, Router, types
from sqlalchemy import select

from database.base import get_db
from database.models import (
    PAID_SOURCES,
    PAYMENT_SOURCE_FEEDBACK,
    Subscription,
    User,
    UserFeedback,
)

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(F.data.startswith("poll_fb:"))
async def process_feedback_poll(callback: types.CallbackQuery) -> None:
    """Handle feedback poll click and grant reward."""
    user_id = callback.from_user.id
    answer = callback.data.split(":")[1]
    poll_id = "inactive_poll_v1"

    async for session in get_db():
        # 0. Check for duplicate to prevent bonus abuse
        dup_stmt = select(UserFeedback).where(
            (UserFeedback.user_id == user_id) & (UserFeedback.feedback_type == poll_id)
        )
        existing = (await session.execute(dup_stmt)).scalar_one_or_none()
        
        if existing:
            await callback.answer("⚠️ Вы уже получили бонус за этот опрос!", show_alert=True)
            return

        # 1. Save feedback
        feedback = UserFeedback(
            user_id=user_id,
            feedback_type=poll_id,
            answer=answer
        )
        session.add(feedback)

        # 2. Grant/Extend PRO status (3 days)
        sub_stmt = select(Subscription).where(Subscription.user_id == user_id)
        sub = (await session.execute(sub_stmt)).scalar_one_or_none()

        now = datetime.now()
        bonus_delta = timedelta(days=3)

        if not sub:
            # Create new subscription
            sub = Subscription(
                user_id=user_id,
                tier="pro",
                starts_at=now,
                expires_at=now + bonus_delta,
                is_active=True,
                auto_renew=False,
                payment_source=PAYMENT_SOURCE_FEEDBACK,
            )
            session.add(sub)
            logger.info(f"Feedback grant: created new PRO sub for {user_id}")
        else:
            # Extend existing OR reactivate expired
            old_expires = sub.expires_at or now

            # If expired, start from now. If active, add to existing expiry.
            base_date = max(old_expires, now)
            sub.expires_at = base_date + bonus_delta
            sub.tier = "pro"
            sub.is_active = True
            sub.auto_renew = False
            # Don't overwrite real payment source — feedback bonus is a freebie
            if sub.payment_source not in PAID_SOURCES:
                sub.payment_source = PAYMENT_SOURCE_FEEDBACK
            logger.info(f"Feedback grant: extended sub for {user_id} until {sub.expires_at}")

        await session.commit()
        break

    # 3. Success notification
    success_text = (
        "✅ <b>Спасибо за честный ответ!</b>\n\n"
        "Ваше мнение поможет нам стать лучше.\n"
        "Как и обещали, мы продлили вам <b>PRO-статус на 3 дня</b>. Пользуйтесь с удовольствием! 🎁"
    )
    
    try:
        await callback.message.edit_text(
            text=success_text,
            parse_mode="HTML"
        )
    except Exception:
        await callback.message.answer(success_text, parse_mode="HTML")
        
    await callback.answer("Бонус начислен! 🎉")
