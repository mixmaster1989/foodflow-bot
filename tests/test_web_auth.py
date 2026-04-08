import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from datetime import datetime, timedelta

from api.main import app
from database.base import get_db
from database.models import User, UserSettings, Subscription

@pytest.fixture(scope="function")
async def client(db_session):
    """Async client with DB dependency override."""
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_web_register_and_onboarding_trigger(client, db_session):
    """Test full web registration flow and reward assignment."""
    payload = {
        "email": "new_user@example.com",
        "password": "securepassword123",
        "name": "Web Traveler"
    }
    
    # 1. Register
    resp = await client.post("/api/auth/web-register", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    
    # 2. Check DB State
    stmt = select(User).where(User.email == "new_user@example.com")
    user = (await db_session.execute(stmt)).scalar_one()
    
    assert user.first_name == "Web Traveler"
    assert user.is_web_only is True
    assert user.id >= 100_000_000_000_000 # 15 digits
    
    # 3. Check Subscription (GIFT)
    sub_stmt = select(Subscription).where(Subscription.user_id == user.id)
    sub = (await db_session.execute(sub_stmt)).scalar_one()
    assert sub.tier == "pro"
    assert sub.is_active is True
    # Should expire in 3 days
    expected_expiry = datetime.now() + timedelta(days=3)
    assert sub.expires_at.date() == expected_expiry.date()
    
    # 4. Check Settings (is_initialized should be False)
    settings_stmt = select(UserSettings).where(UserSettings.user_id == user.id)
    settings = (await db_session.execute(settings_stmt)).scalar_one()
    assert settings.is_initialized is False

    # 5. PERFORM ONBOARDING (Update settings)
    headers = {"Authorization": f"Bearer {data['access_token']}"}
    onboarding_payload = {
        "goal": "lose_weight",
        "gender": "male",
        "age": 30,
        "height": 180,
        "weight": 85.5,
        "calorie_goal": 2100,
        "is_initialized": True
    }
    update_resp = await client.patch("/api/auth/settings", headers=headers, json=onboarding_payload)
    assert update_resp.status_code == 200
    assert update_resp.json()["is_initialized"] is True
    assert update_resp.json()["weight"] == 85.5
    
    # Verify in DB again
    await db_session.refresh(settings)
    assert settings.is_initialized is True
    assert settings.weight == 85.5

@pytest.mark.asyncio
async def test_web_login_flow(client, db_session):
    """Test email/password login."""
    # Pre-create a web user
    from api.auth import pwd_context
    hashed = pwd_context.hash("mypassword")
    user = User(id=999_888_777_666_555, email="login@test.com", password_hash=hashed, is_web_only=True)
    db_session.add(user)
    await db_session.commit()
    
    # 1. Correct Login
    resp = await client.post("/api/auth/web-login", json={"email": "login@test.com", "password": "mypassword"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()
    
    # 2. Wrong Password
    resp = await client.post("/api/auth/web-login", json={"email": "login@test.com", "password": "wrong"})
    assert resp.status_code == 401
    assert "Неверный пароль" in resp.json()["detail"]
    
    # 3. Non-existent email
    resp = await client.post("/api/auth/web-login", json={"email": "none@test.com", "password": "any"})
    assert resp.status_code == 401

@pytest.mark.asyncio
async def test_duplicate_email_registration(client, db_session):
    """Test that duplicate email registration fails."""
    user = User(id=111222, email="duplicate@test.com", is_web_only=True)
    db_session.add(user)
    await db_session.commit()
    
    payload = {
        "email": "DUPLICATE@test.com", # Check case insensitivity
        "password": "pass",
        "name": "N"
    }
    resp = await client.post("/api/auth/web-register", json=payload)
    assert resp.status_code == 409
    assert "уже зарегистрирован" in resp.json()["detail"]
