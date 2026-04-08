"""
Tests for marketing analytics service.
"""
import io
import os
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

# Set test environment variables before importing modules
os.environ.setdefault('DATABASE_URL', 'sqlite+aiosqlite:///:memory:')
os.environ.setdefault('BOT_TOKEN', 'test-token')
os.environ.setdefault('OPENROUTER_API_KEY', 'test-key')
os.environ.setdefault('JWT_SECRET_KEY', 'test-secret')
os.environ.setdefault('GLOBAL_PASSWORD', 'test-password')

from database.base import Base, engine
from database.models import (
    ConsumptionLog,
    ReferralEvent,
    Subscription,
    User,
    UserFeedback,
    UserSettings,
)
from services.marketing_analytics import (
    export_csv,
    get_acquisition_funnel,
    get_daily_digest,
    get_hourly_activity,
    get_retention_metrics,
    get_tier_distribution,
)


@pytest.fixture(scope="function")
async def db_session():
    """Create a fresh in-memory database for each test."""
    async_session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_session_factory() as session:
        yield session
        await session.rollback()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def _seed_users(session, count=5, days_ago=1):
    """Helper to create users."""
    users = []
    for i in range(count):
        u = User(
            id=1000 + i,
            username=f"user_{i}",
            first_name=f"User{i}",
            created_at=datetime.now() - timedelta(days=days_ago),
        )
        session.add(u)
        users.append(u)
    await session.commit()
    return users


async def _seed_logs(session, user_ids, count_per_user=3, days_ago=1, hour=12):
    """Helper to create consumption logs."""
    target_date = datetime.now() - timedelta(days=days_ago)
    target_date = target_date.replace(hour=hour, minute=0, second=0)

    for uid in user_ids:
        for j in range(count_per_user):
            log = ConsumptionLog(
                user_id=uid,
                product_name=f"Product {j}",
                calories=200.0,
                protein=15.0,
                fat=8.0,
                carbs=25.0,
                date=target_date + timedelta(hours=j),
            )
            session.add(log)
    await session.commit()


class TestDailyDigest:
    """Tests for get_daily_digest()."""

    @pytest.mark.asyncio
    async def test_empty_db(self, db_session):
        """Digest should not crash on empty database."""
        result = await get_daily_digest()
        assert isinstance(result, str)
        assert "Маркетинг-сводка" in result
        assert "DAU: 0" in result

    @pytest.mark.asyncio
    async def test_with_data(self, db_session):
        """Digest should reflect correct counts."""
        users = await _seed_users(db_session, count=3, days_ago=1)
        await _seed_logs(db_session, [u.id for u in users[:2]], count_per_user=4, days_ago=1)

        result = await get_daily_digest()
        assert "+3 новых" in result
        assert "DAU: 2" in result
        assert "логов еды: 8" in result


class TestAcquisitionFunnel:
    """Tests for get_acquisition_funnel()."""

    @pytest.mark.asyncio
    async def test_funnel_returns_table(self, db_session):
        """Funnel should return a formatted table."""
        await _seed_users(db_session, count=2, days_ago=1)
        result = await get_acquisition_funnel(days=3)
        assert "Воронка" in result
        assert "Новые" in result

    @pytest.mark.asyncio
    async def test_funnel_with_referrals(self, db_session):
        """Funnel should count referral signups."""
        users = await _seed_users(db_session, count=2, days_ago=1)
        event = ReferralEvent(
            referrer_id=users[0].id,
            invitee_id=users[1].id,
            event_type="signup",
            tier="pro",
            created_at=datetime.now() - timedelta(days=1),
        )
        db_session.add(event)
        await db_session.commit()

        result = await get_acquisition_funnel(days=3)
        assert isinstance(result, str)


class TestRetentionMetrics:
    """Tests for get_retention_metrics()."""

    @pytest.mark.asyncio
    async def test_empty_db(self, db_session):
        """Should not crash on empty DB."""
        result = await get_retention_metrics()
        assert "Удержание" in result
        assert "DAU" in result

    @pytest.mark.asyncio
    async def test_dau_wau_mau(self, db_session):
        """Should calculate DAU/WAU/MAU correctly."""
        users = await _seed_users(db_session, count=5, days_ago=10)

        # DAU: 2 users active yesterday
        await _seed_logs(db_session, [users[0].id, users[1].id], count_per_user=1, days_ago=1)
        # WAU: 1 more user active 3 days ago
        await _seed_logs(db_session, [users[2].id], count_per_user=1, days_ago=3)
        # MAU: 1 more user active 15 days ago
        await _seed_logs(db_session, [users[3].id], count_per_user=1, days_ago=15)

        result = await get_retention_metrics()
        assert "DAU (вчера): 2" in result
        assert "WAU (7 дней): 3" in result
        assert "MAU (30 дней): 4" in result


class TestTierDistribution:
    """Tests for get_tier_distribution()."""

    @pytest.mark.asyncio
    async def test_empty_db(self, db_session):
        """Should not crash on empty DB."""
        result = await get_tier_distribution()
        assert "Распределение тарифов" in result

    @pytest.mark.asyncio
    async def test_counts(self, db_session):
        """Should count each tier correctly."""
        users = await _seed_users(db_session, count=4, days_ago=5)

        for tier, uid in [("basic", users[0].id), ("pro", users[1].id), ("pro", users[2].id)]:
            sub = Subscription(user_id=uid, tier=tier, is_active=True, starts_at=datetime.now())
            db_session.add(sub)
        await db_session.commit()

        result = await get_tier_distribution()
        assert "Basic: 1" in result
        assert "Pro: 2" in result
        assert "Всего платных: 3" in result


class TestHourlyActivity:
    """Tests for get_hourly_activity()."""

    @pytest.mark.asyncio
    async def test_empty_db(self, db_session):
        """Should not crash on empty DB."""
        result = await get_hourly_activity(days=3)
        assert "Активность по часам" in result

    @pytest.mark.asyncio
    async def test_peak_hour(self, db_session):
        """Should identify the peak hour."""
        users = await _seed_users(db_session, count=1, days_ago=5)
        # Add 5 logs at hour 14
        await _seed_logs(db_session, [users[0].id], count_per_user=5, days_ago=1, hour=14)

        result = await get_hourly_activity(days=3)
        assert "Пиковый час: 14:00" in result


class TestCsvExport:
    """Tests for export_csv()."""

    @pytest.mark.asyncio
    async def test_csv_header(self, db_session):
        """CSV should have correct headers."""
        csv_io = await export_csv(days=3)
        content = csv_io.getvalue().decode("utf-8")
        assert "DAILY STATS" in content
        assert "Date" in content
        assert "New Users" in content
        assert "ACQUISITION SOURCES" in content

    @pytest.mark.asyncio
    async def test_csv_with_data(self, db_session):
        """CSV should contain data rows."""
        await _seed_users(db_session, count=2, days_ago=1)
        await _seed_logs(db_session, [1000, 1001], count_per_user=2, days_ago=1)

        csv_io = await export_csv(days=3)
        content = csv_io.getvalue().decode("utf-8")
        # Check that yesterday's row has data
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        assert yesterday in content
        assert "DAILY STATS" in content
        assert "ACQUISITION SOURCES" in content
