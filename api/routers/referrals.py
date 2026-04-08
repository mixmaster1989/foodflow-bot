from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from aiogram import Bot

from api.auth import CurrentUser, DBSession
from api.schemas import (
    ReferralMeResponse,
    ReferralRewardPendingRead,
    ReferralActivateRequest,
    ReferralGenerateLinkRequest,
    ReferralGenerateLinkResponse,
)
from config import settings
from database.models import ReferralEvent, ReferralReward, User
from services.referral_service import ReferralService


router = APIRouter()

_BOT_USERNAME_CACHE: Optional[str] = None


async def _get_bot_username() -> str:
    global _BOT_USERNAME_CACHE
    if _BOT_USERNAME_CACHE:
        return _BOT_USERNAME_CACHE

    bot = Bot(token=settings.BOT_TOKEN)
    try:
        me = await bot.get_me()
        _BOT_USERNAME_CACHE = me.username
        return _BOT_USERNAME_CACHE
    finally:
        await bot.session.close()


@router.get("/me", response_model=ReferralMeResponse)
async def get_my_referrals(user: CurrentUser, session: DBSession):
    """Return referral stats, rewards and personal link for current user."""
    # Basic stats from events
    stmt = select(ReferralEvent).where(ReferralEvent.referrer_id == user.id)
    events = (await session.execute(stmt)).scalars().all()

    signup_count = sum(1 for e in events if e.event_type == "signup")
    paid_count = sum(1 for e in events if e.event_type == "paid")

    # Pending rewards
    pending_stmt = select(ReferralReward).where(
        ReferralReward.user_id == user.id,
        ReferralReward.is_active.is_(False),
    )
    pending = (await session.execute(pending_stmt)).scalars().all()

    # Active rewards
    active_stmt = select(ReferralReward).where(
        ReferralReward.user_id == user.id,
        ReferralReward.is_active.is_(True),
    )
    active = (await session.execute(active_stmt)).scalars().all()

    # Aggregate active bonuses
    active_basic = sum(r.days for r in active if r.reward_type == "basic_days")
    active_pro = sum(r.days for r in active if r.reward_type == "pro_days")
    active_curator = sum(r.days for r in active if r.reward_type == "curator_days")

    # Referral progress
    db_user = await session.get(User, user.id)
    ref_paid_count = db_user.ref_paid_count if db_user and db_user.ref_paid_count else 0
    has_month_pro_bonus = any(
        r.reward_type == "pro_days" and r.source == "ref_10_paid"
        for r in list(pending) + list(active)
    )

    # Current referral link data
    referral_link: Optional[str] = None
    referral_token_expires_at: Optional[datetime] = None
    if db_user and db_user.referral_token:
        bot_username = await _get_bot_username()
        referral_link = f"https://t.me/{bot_username}?start=ref_{db_user.referral_token}"
        referral_token_expires_at = db_user.referral_token_expires_at

    return ReferralMeResponse(
        signup_count=signup_count,
        paid_count=paid_count,
        ref_paid_count=ref_paid_count,
        has_month_pro_bonus=has_month_pro_bonus,
        pending_rewards=[
            ReferralRewardPendingRead(
                id=r.id,
                reward_type=r.reward_type,
                days=r.days,
                source=r.source,
            )
            for r in pending
        ],
        active_basic_days=active_basic,
        active_pro_days=active_pro,
        active_curator_days=active_curator,
        referral_link=referral_link,
        referral_token_expires_at=referral_token_expires_at,
    )


@router.post("/generate_link", response_model=ReferralGenerateLinkResponse)
async def generate_link(
    payload: ReferralGenerateLinkRequest,
    user: CurrentUser,
):
    """Generate or refresh personal referral link via API."""
    days = payload.days if payload.days is not None else 30
    result = await ReferralService.generate_referral_token(user_id=user.id, days=days)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to generate referral link",
        )

    token, expires_at = result
    bot_username = await _get_bot_username()
    link = f"https://t.me/{bot_username}?start=ref_{token}"

    return ReferralGenerateLinkResponse(
        referral_link=link,
        referral_token_expires_at=expires_at,
    )


@router.post("/activate_reward")
async def activate_reward_api(
    payload: ReferralActivateRequest,
    user: CurrentUser,
):
    """Activate referral reward for current user via API."""
    ok = await ReferralService.activate_reward(user_id=user.id, reward_id=payload.reward_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot activate reward (limit reached or not found)",
        )
    return {"status": "ok"}

