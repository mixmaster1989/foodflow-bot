import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select

from database.base import get_db
from database.models import User, Subscription, ReferralEvent, ReferralReward


logger = logging.getLogger(__name__)


class ReferralService:
    """Service layer for referral accounting and rewards."""

    @staticmethod
    async def _get_user(session, user_id: int) -> Optional[User]:
        return await session.get(User, user_id)

    @staticmethod
    async def generate_referral_token(
        user_id: int,
        days: Optional[int] = None,
    ) -> Optional[tuple[str, Optional[datetime]]]:
        """
        (Re)generate personal referral token for a user.

        days:
          - None or 0 -> no expiry (бессрочно)
          - N > 0     -> valid for N days from now
        """
        import uuid

        async for session in get_db():
            user = await session.get(User, user_id)
            if not user:
                logger.warning(f"[REFERRAL] Cannot generate referral token: user {user_id} not found")
                return None

            token = str(uuid.uuid4())[:12]
            now = datetime.now()

            if not days:
                expires_at: Optional[datetime] = None
            else:
                expires_at = now + timedelta(days=days)

            user.referral_token = token
            user.referral_token_expires_at = expires_at

            await session.commit()
            return token, expires_at

        return None

    @staticmethod
    async def handle_successful_payment(user_id: int, tier: str) -> None:
        """
        Called after any successful subscription payment (Stars or RUB).

        - Records referral 'paid' event for:
          - invited_by_id (обычная рефка)
          - curator_id (кураторская рефка; бонус только если у куратора активен Curator)
        - Creates referral_rewards entries according to business rules.
        """
        async for session in get_db():
            user = await ReferralService._get_user(session, user_id)
            if not user:
                logger.warning(f"[REFERRAL] User {user_id} not found on payment")
                break

            now = datetime.now()

            # 1) Обычная рефка (invited_by_id)
            if user.invited_by_id:
                referrer = await ReferralService._get_user(session, user.invited_by_id)
                if referrer:
                    # Log event
                    event = ReferralEvent(
                        referrer_id=referrer.id,
                        invitee_id=user.id,
                        event_type="paid",
                        tier=tier,
                        created_at=now,
                    )
                    session.add(event)

                    # Increment paid count and check for milestone 10
                    referrer.ref_paid_count = (referrer.ref_paid_count or 0) + 1

                    # +5 дней Basic за каждого платящего
                    reward = ReferralReward(
                        user_id=referrer.id,
                        reward_type="basic_days",
                        days=5,
                        source="ref_invite_paid",
                    )
                    session.add(reward)

                    # Однократный бонус 1 месяц Pro за 10 разных платящих
                    if referrer.ref_paid_count == 10:
                        pro_reward = ReferralReward(
                            user_id=referrer.id,
                            reward_type="pro_days",
                            days=30,
                            source="ref_10_paid",
                        )
                        session.add(pro_reward)

            # 2) Кураторская рефка: бонус только активным кураторам
            if user.curator_id:
                curator = await ReferralService._get_user(session, user.curator_id)
                if curator:
                    # Explicitly fetch subscription to avoid lazy load error
                    from database.models import Subscription
                    sub_stmt = select(Subscription).where(Subscription.user_id == curator.id)
                    cur_sub = (await session.execute(sub_stmt)).scalar_one_or_none()

                    if cur_sub and cur_sub.tier == "curator" and cur_sub.is_active:
                        event = ReferralEvent(
                            referrer_id=curator.id,
                            invitee_id=user.id,
                            event_type="paid",
                            tier=tier,
                            created_at=now,
                        )
                        session.add(event)

                        curator_reward = ReferralReward(
                            user_id=curator.id,
                            reward_type="curator_days",
                            days=5,
                            source="curator_ref_paid",
                        )
                        session.add(curator_reward)

            await session.commit()
            break

    # --- Bonus activation logic will be used from handlers/referrals.py ---

    @staticmethod
    async def _get_active_bonus_days(session, user_id: int, reward_type: str) -> int:
        """
        Approximate count of active/planned bonus days for a given reward_type.
        For now we only use referral_rewards table (activated entries).
        """
        stmt = select(ReferralReward).where(
            ReferralReward.user_id == user_id,
            ReferralReward.reward_type == reward_type,
            ReferralReward.is_active.is_(True),
        )
        rewards = (await session.execute(stmt)).scalars().all()
        return sum(r.days for r in rewards)

    @staticmethod
    async def activate_reward(user_id: int, reward_id: int) -> bool:
        """
        Activate a specific referral reward for user.

        - Checks ownership and 365-day limit.
        - Extends or creates Subscription according to reward_type.
        """
        async for session in get_db():
            reward = await session.get(ReferralReward, reward_id)
            if not reward or reward.user_id != user_id or reward.is_active:
                return False

            # Enforce 365-day limit per reward_type
            current_days = await ReferralService._get_active_bonus_days(
                session, user_id, reward.reward_type
            )
            if current_days + reward.days > 365:
                logger.info(
                    f"[REFERRAL] User {user_id} reached bonus limit for {reward.reward_type}: "
                    f"{current_days} + {reward.days} > 365"
                )
                return False

            user = await session.get(User, user_id)
            if not user:
                return False

            # Explicitly fetch subscription instead of using user.subscription (lazy load fails in async)
            from database.models import Subscription
            sub_stmt = select(Subscription).where(Subscription.user_id == user_id)
            sub = (await session.execute(sub_stmt)).scalar_one_or_none()
            
            now = datetime.now()

            # Determine target tier from reward_type
            if reward.reward_type == "basic_days":
                target_tier = "basic"
            elif reward.reward_type == "pro_days":
                target_tier = "pro"
            elif reward.reward_type == "curator_days":
                target_tier = "curator"
            else:
                logger.error(f"[REFERRAL] Unknown reward_type {reward.reward_type} for reward {reward.id}")
                return False

            # Apply simple stacking rules:
            # - If no subscription: start new at target_tier for reward.days
            # - If subscription at same tier: extend expires_at
            # - If different tier: if target is higher priority, replace; otherwise extend after, approximated by extending expires_at
            if not sub:
                expires = now + timedelta(days=reward.days)
                sub = Subscription(
                    user_id=user_id,
                    tier=target_tier,
                    starts_at=now,
                    expires_at=expires,
                    is_active=True,
                    auto_renew=False,
                )
                session.add(sub)
            else:
                # Basic priority ordering
                priority = {"basic": 1, "pro": 2, "curator": 3}
                current_tier = sub.tier or "free"
                current_priority = priority.get(current_tier, 0)
                target_priority = priority.get(target_tier, 0)

                # Ensure expires_at is set
                base_start = sub.expires_at or now

                if current_tier == target_tier:
                    # Extend same tier
                    sub.expires_at = base_start + timedelta(days=reward.days)
                elif target_priority > current_priority:
                    # Upgrade: switch tier and set new period from now
                    sub.tier = target_tier
                    sub.starts_at = now
                    sub.expires_at = now + timedelta(days=reward.days)
                    sub.is_active = True
                    sub.auto_renew = False
                else:
                    # Lower or equal priority bonus: approximate by extending expiry
                    sub.expires_at = base_start + timedelta(days=reward.days)

            # Mark reward as activated
            reward.is_active = True
            reward.activated_at = now

            # Log event
            event = ReferralEvent(
                referrer_id=user_id,
                invitee_id=user_id,
                event_type="bonus_activated",
                tier=target_tier,
                created_at=now,
            )
            session.add(event)

            await session.commit()
            return True

        return False


