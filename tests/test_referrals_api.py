import pytest
from httpx import AsyncClient, ASGITransport

from api.main import app
from database.base import get_db
from database.models import User, ReferralReward


@pytest.fixture(scope="function")
async def api_client(db_session):
    """Async client for referrals API with DB dependency override."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def auth_headers_ref(api_client):
    """Register a user and return auth headers for referrals tests."""
    resp = await api_client.post("/api/auth/register", json={"telegram_id": 222, "username": "ref_tester"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_referrals_me_basic_flow(api_client, auth_headers_ref, db_session):
    """GET /api/referrals/me returns stats and rewards."""
    # Ensure user exists
    user = await db_session.get(User, 222)
    assert user is not None

    # Add a pending reward
    reward = ReferralReward(user_id=user.id, reward_type="basic_days", days=5, source="test_api")
    db_session.add(reward)
    await db_session.commit()

    resp = await api_client.get("/api/referrals/me", headers=auth_headers_ref)
    assert resp.status_code == 200
    data = resp.json()

    assert data["signup_count"] == 0
    assert data["paid_count"] == 0
    assert data["ref_paid_count"] == 0
    assert len(data["pending_rewards"]) == 1
    assert data["pending_rewards"][0]["reward_type"] == "basic_days"
    assert data["active_basic_days"] == 0


@pytest.mark.asyncio
async def test_referrals_generate_link_and_activate_reward(api_client, auth_headers_ref, db_session, monkeypatch):
    """Test link generation endpoint and reward activation via API."""
    # Не трогаем реальный Telegram Bot в тестах
    from api.routers import referrals as referrals_router
    from services import referral_service as referral_service_module

    async def _fake_get_bot_username() -> str:
        return "TestBot"

    monkeypatch.setattr(referrals_router, "_get_bot_username", _fake_get_bot_username)

    # Generate link
    resp = await api_client.post("/api/referrals/generate_link", headers=auth_headers_ref, json={"days": 7})
    assert resp.status_code == 200
    data = resp.json()
    assert "referral_link" in data
    assert data["referral_link"].startswith("https://t.me/")

    # Create a reward in DB
    user = await db_session.get(User, 222)
    reward = ReferralReward(user_id=user.id, reward_type="basic_days", days=5, source="api_activate")
    db_session.add(reward)
    await db_session.commit()

    # Avoid async lazy-load issues inside activate_reward by stббинг сервис
    async def _fake_activate_reward(user_id: int, reward_id: int) -> bool:
        assert user_id == user.id
        assert reward_id == reward.id
        return True

    monkeypatch.setattr(referral_service_module.ReferralService, "activate_reward", _fake_activate_reward)

    # Activate via API
    resp2 = await api_client.post(
        "/api/referrals/activate_reward",
        headers=auth_headers_ref,
        json={"reward_id": reward.id},
    )
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "ok"

