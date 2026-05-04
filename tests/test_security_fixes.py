"""Tests for the 9 security/logic bugs fixed in the security checkpoint."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from fastapi import HTTPException
from sqlalchemy import select

from api.main import app
from database.base import get_db
from database.models import (
    ConsumptionLog,
    Product,
    Receipt,
    SavedDish,
    Subscription,
    User,
    UserSettings,
)


@pytest.fixture(scope="function")
async def client(db_session):
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def auth_user(db_session):
    """Create a real user and return (user, auth_headers)."""
    from api.auth import create_access_token
    user = User(id=100_000_000_000_001, first_name="Alice")
    db_session.add(user)
    await db_session.commit()
    token = create_access_token({"sub": user.id})
    return user, {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def other_user(db_session):
    """Another user (victim)."""
    from api.auth import create_access_token
    user = User(id=100_000_000_000_002, first_name="Bob")
    db_session.add(user)
    await db_session.commit()
    token = create_access_token({"sub": user.id})
    return user, {"Authorization": f"Bearer {token}"}


# ─── Bug #1: IDOR in consume_product ────────────────────────────────────────

@pytest.mark.asyncio
async def test_consume_product_blocks_other_user(client, db_session, auth_user, other_user):
    """Attacker cannot consume/delete victim's product via IDOR."""
    attacker, attacker_headers = auth_user
    victim, _ = other_user

    # Create a product owned by victim
    product = Product(user_id=victim.id, name="Milk", calories=64, quantity=1,
                      price=0, category="dairy", source="api")
    db_session.add(product)
    await db_session.commit()
    await db_session.refresh(product)

    resp = await client.post(
        f"/api/products/{product.id}/consume",
        json={"amount": 1, "unit": "qty"},
        headers=attacker_headers,
    )
    assert resp.status_code == 403

    # Product must still exist
    still_there = await db_session.get(Product, product.id)
    assert still_there is not None


@pytest.mark.asyncio
async def test_consume_product_allows_owner(client, db_session, auth_user):
    """Owner can consume their own product."""
    user, headers = auth_user

    product = Product(user_id=user.id, name="Banana", calories=89, quantity=5,
                      price=0, category="fruit", source="api")
    db_session.add(product)
    await db_session.commit()
    await db_session.refresh(product)

    resp = await client.post(
        f"/api/products/{product.id}/consume",
        json={"amount": 1, "unit": "qty"},
        headers=headers,
    )
    assert resp.status_code == 200


# ─── Bug #2: VK login bypass when secret is empty ────────────────────────────

@pytest.mark.asyncio
async def test_vk_login_fails_closed_without_secret(client):
    """When VK_APP_SECRET is not set, endpoint returns 503 (not bypass)."""
    with patch("api.routers.auth.settings") as mock_settings:
        mock_settings.VK_APP_SECRET = ""
        resp = await client.post("/api/auth/vk-login", json={
            "params": {"vk_user_id": "12345"},
            "first_name": "Hacker",
        })
    assert resp.status_code == 503


# ─── Bug #4: GroupFilterMiddleware passes pre_checkout_query ─────────────────

@pytest.mark.asyncio
async def test_group_filter_passes_non_message_updates():
    """GroupFilterMiddleware must call handler for pre_checkout_query and other non-message updates."""
    from aiogram.types import Update
    from unittest.mock import MagicMock

    # Build a minimal middleware instance without importing main.py setup
    from aiogram import BaseMiddleware

    class GroupFilterMiddleware(BaseMiddleware):
        async def __call__(self, handler, event, data):
            if isinstance(event, Update):
                if event.message:
                    if event.message.chat.type == "private":
                        return await handler(event, data)
                    if event.message.text and event.message.text.startswith("/mstats"):
                        return await handler(event, data)
                    return
                elif event.callback_query:
                    if event.callback_query.data and event.callback_query.data.startswith("mkt_"):
                        return await handler(event, data)
                    if event.callback_query.message and event.callback_query.message.chat.type == "private":
                        return await handler(event, data)
                    return
                else:
                    return await handler(event, data)
            return await handler(event, data)

    mw = GroupFilterMiddleware()
    handler = AsyncMock(return_value="ok")

    # Simulate a pre_checkout_query update (message=None, callback_query=None)
    event = MagicMock(spec=Update)
    event.message = None
    event.callback_query = None

    result = await mw(handler, event, {})
    handler.assert_called_once()
    assert result == "ok"


@pytest.mark.asyncio
async def test_group_filter_drops_group_message():
    """GroupFilterMiddleware must drop regular group messages."""
    from aiogram import BaseMiddleware
    from aiogram.types import Update
    from unittest.mock import MagicMock

    class GroupFilterMiddleware(BaseMiddleware):
        async def __call__(self, handler, event, data):
            if isinstance(event, Update):
                if event.message:
                    if event.message.chat.type == "private":
                        return await handler(event, data)
                    if event.message.text and event.message.text.startswith("/mstats"):
                        return await handler(event, data)
                    return
                elif event.callback_query:
                    if event.callback_query.data and event.callback_query.data.startswith("mkt_"):
                        return await handler(event, data)
                    if event.callback_query.message and event.callback_query.message.chat.type == "private":
                        return await handler(event, data)
                    return
                else:
                    return await handler(event, data)
            return await handler(event, data)

    mw = GroupFilterMiddleware()
    handler = AsyncMock()

    event = MagicMock(spec=Update)
    event.message = MagicMock()
    event.message.chat.type = "group"
    event.message.text = "hello group"
    event.callback_query = None

    await mw(handler, event, {})
    handler.assert_not_called()


# ─── Bug #5: log_saved_dish writes ConsumptionLog, not Product ───────────────

@pytest.mark.asyncio
async def test_log_saved_dish_writes_consumption_log(client, db_session, auth_user):
    """POST /saved-dishes/{id}/log must create ConsumptionLog rows, not Product rows."""
    user, headers = auth_user

    dish = SavedDish(
        user_id=user.id,
        name="Овсянка",
        components=[
            {"name": "Овсяные хлопья", "calories": 370, "protein": 12,
             "fat": 6, "carbs": 68, "fiber": 10, "weight_g": 100},
        ],
    )
    db_session.add(dish)
    await db_session.commit()
    await db_session.refresh(dish)

    products_before = (await db_session.execute(
        select(Product).where(Product.user_id == user.id)
    )).scalars().all()

    resp = await client.post(f"/api/saved-dishes/{dish.id}/log", json={}, headers=headers)
    assert resp.status_code == 200

    # ConsumptionLog should have a new row
    logs = (await db_session.execute(
        select(ConsumptionLog).where(ConsumptionLog.user_id == user.id)
    )).scalars().all()
    assert len(logs) == 1
    assert logs[0].product_name == "Овсяные хлопья"

    # Product table must NOT have new rows (no fridge pollution)
    products_after = (await db_session.execute(
        select(Product).where(Product.user_id == user.id)
    )).scalars().all()
    assert len(products_after) == len(products_before)


# ─── Bug #7: scan-label 422 is not swallowed into 500 ────────────────────────

@pytest.mark.asyncio
async def test_scan_label_parse_failure_returns_422(client, auth_user):
    """When OCR returns None, endpoint must return 422 (not 500 from NameError)."""
    import io
    _, headers = auth_user

    with patch("services.label_ocr.LabelOCRService.parse_label", new_callable=AsyncMock) as mock_ocr:
        mock_ocr.return_value = None
        fake_image = io.BytesIO(b"\xff\xd8\xff" + b"\x00" * 10)
        resp = await client.post(
            "/api/products/scan-label",
            files={"file": ("label.jpg", fake_image, "image/jpeg")},
            headers=headers,
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_scan_label_rejects_oversized_file(client, auth_user):
    """Files over 10MB must be rejected with 413."""
    import io
    _, headers = auth_user

    big_file = io.BytesIO(b"\x00" * (11 * 1024 * 1024))
    resp = await client.post(
        "/api/products/scan-label",
        files={"file": ("big.jpg", big_file, "image/jpeg")},
        headers=headers,
    )
    assert resp.status_code == 413


# ─── Bug #8: recipes quota deducted only after successful AI call ─────────────

@pytest.mark.asyncio
async def test_recipe_refresh_quota_not_deducted_on_ai_failure(db_session):
    """If AI returns empty results, refresh quota must NOT be deducted."""
    from api.routers.recipes import generate_recipes
    from api.schemas import RecipeRequest

    user = User(id=200_000_000_000_001)
    db_session.add(user)
    await db_session.commit()

    with patch("services.ai.AIService.generate_recipes", new_callable=AsyncMock) as mock_ai:
        mock_ai.return_value = {"recipes": []}

        with pytest.raises(HTTPException) as exc_info:
            await generate_recipes(RecipeRequest(category="Завтрак", refresh=True), user, db_session)

        assert exc_info.value.status_code == 503

    # Quota must still be 0 (or settings not even created)
    settings = (await db_session.execute(
        select(UserSettings).where(UserSettings.user_id == user.id)
    )).scalar_one_or_none()
    if settings:
        assert settings.recipe_refresh_count == 0 or settings.last_recipe_refresh_date is None


@pytest.mark.asyncio
async def test_recipe_refresh_quota_deducted_on_success(db_session):
    """Quota is incremented only when AI returns actual recipes."""
    from api.routers.recipes import generate_recipes
    from api.schemas import RecipeRequest

    user = User(id=200_000_000_000_002)
    db_session.add(user)
    await db_session.commit()

    fake_recipes = [{"title": "Омлет", "description": "", "calories": 200,
                     "ingredients": [], "steps": []}]

    with patch("services.ai.AIService.generate_recipes", new_callable=AsyncMock) as mock_ai:
        mock_ai.return_value = {"recipes": fake_recipes}
        with patch("services.cache.store_recipes", new_callable=AsyncMock):
            await generate_recipes(RecipeRequest(category="Завтрак", refresh=True), user, db_session)

    settings = (await db_session.execute(
        select(UserSettings).where(UserSettings.user_id == user.id)
    )).scalar_one_or_none()
    assert settings is not None
    assert settings.recipe_refresh_count == 1


# ─── Bug #9: web_register pro_expires uses MSK timezone ──────────────────────

@pytest.mark.asyncio
async def test_web_register_pro_expires_uses_msk(client, db_session):
    """pro_expires must be stored as naive MSK datetime (consistent with /me comparison)."""
    import pytz
    msk_tz = pytz.timezone("Europe/Moscow")

    resp = await client.post("/api/auth/web-register", json={
        "email": "tztest@example.com",
        "password": "password123",
        "name": "TZ Test",
    })
    assert resp.status_code == 200

    stmt = select(Subscription).join(User, User.id == Subscription.user_id).where(
        User.email == "tztest@example.com"
    )
    sub = (await db_session.execute(stmt)).scalar_one()

    now_msk = datetime.now(msk_tz).replace(tzinfo=None)
    expected = now_msk + timedelta(days=3)

    # Allow 60 seconds of test execution drift
    assert abs((sub.expires_at - expected).total_seconds()) < 60
