from sqlalchemy import text

from database.models import User, ReferralEvent, ReferralReward


async def test_referral_tables_exist_and_columns_present(db_session):
    """
    Ensure that referral tables and new user columns exist after metadata.create_all.
    """
    # Helper to check table exists
    async def table_exists(name: str) -> bool:
        result = await db_session.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name=:name"),
            {"name": name},
        )
        return result.scalar_one_or_none() is not None

    # Helper to get column names
    async def columns(table: str) -> set[str]:
        result = await db_session.execute(text(f"PRAGMA table_info({table})"))
        return {row[1] for row in result.fetchall()}

    assert await table_exists("referral_events")
    assert await table_exists("referral_rewards")

    user_cols = await columns("users")
    assert "invited_by_id" in user_cols
    assert "ref_paid_count" in user_cols


async def test_create_referral_event_and_reward(db_session):
    """
    Basic CRUD: create ReferralEvent and ReferralReward and read them back.
    """
    # Create referrer and invitee
    referrer = User(id=1, username="referrer")
    invitee = User(id=2, username="invitee", invited_by_id=1)
    db_session.add_all([referrer, invitee])
    await db_session.commit()

    event = ReferralEvent(
        referrer_id=referrer.id,
        invitee_id=invitee.id,
        event_type="paid",
        tier="pro",
    )
    reward = ReferralReward(
        user_id=referrer.id,
        reward_type="basic_days",
        days=5,
        source="ref_invite_paid",
    )
    db_session.add_all([event, reward])
    await db_session.commit()

    # Reload
    loaded_event = await db_session.get(ReferralEvent, event.id)
    loaded_reward = await db_session.get(ReferralReward, reward.id)
    loaded_referrer = await db_session.get(User, referrer.id)

    assert loaded_event is not None
    assert loaded_event.event_type == "paid"
    assert loaded_event.tier == "pro"
    assert loaded_event.created_at is not None

    assert loaded_reward is not None
    assert loaded_reward.reward_type == "basic_days"
    assert loaded_reward.days == 5
    assert loaded_reward.is_active is False
    assert loaded_reward.created_at is not None
    assert loaded_reward.activated_at is None

    # ref_paid_count default should be 0
    assert (loaded_referrer.ref_paid_count or 0) == 0

