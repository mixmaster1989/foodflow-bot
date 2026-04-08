import pytest
from httpx import AsyncClient, ASGITransport
from datetime import datetime, timedelta, date as py_date
import pytz
from sqlalchemy import select
from unittest.mock import patch, AsyncMock

from api.main import app
from database.base import get_db
from database.models import User, UserSettings, Subscription, ConsumptionLog, WaterLog, Product, WeightLog
import api.auth

# Moscow Timezone
MSK_TZ = pytz.timezone("Europe/Moscow")

@pytest.fixture(scope="function")
async def client(db_session):
    """Async client with DB dependency override."""
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()

@pytest.fixture
async def auth_headers(client):
    """Register a user and return auth headers."""
    resp = await client.post("/api/auth/register", json={"telegram_id": 111, "username": "test_pilot"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.mark.asyncio
async def test_products_full_lifecycle(client, auth_headers, db_session):
    """Test creating, getting, consuming and deleting products."""
    # 1. Create a product
    payload = {
        "name": "Greek Yogurt",
        "price": 85.5,
        "quantity": 2,
        "weight_g": 300,
        "category": "Dairy",
        "calories": 60,
        "protein": 10,
        "fat": 0,
        "carbs": 4,
        "fiber": 0
    }
    resp = await client.post("/api/products", headers=auth_headers, json=payload)
    assert resp.status_code == 201
    prod_id = resp.json()["id"]
    assert resp.json()["name"] == "Greek Yogurt"
    
    # 2. List products
    resp = await client.get("/api/products", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["id"] == prod_id
    
    # 3. Consume part of the product (by quantity)
    consume_payload = {"amount": 0.5, "unit": "qty"}
    resp = await client.post(f"/api/products/{prod_id}/consume", headers=auth_headers, json=consume_payload)
    assert resp.status_code == 200
    assert "Consumed 0.5 units" in resp.json()["message"]
    # Check log values: 0.5 units of 60 cal/100g. 
    # Logic in code: if unit=qty and weight_g exists -> factor = ( (300/2) * 0.5 ) / 100 = 0.75
    # calories = 60 * 0.75 = 45.0
    assert resp.json()["logged"]["calories"] == 45.0
    
    # 4. Check if product quantity updated in DB
    prod = await db_session.get(Product, prod_id)
    assert prod.quantity == 1.5
    
    # 5. Delete product
    resp = await client.delete(f"/api/products/{prod_id}", headers=auth_headers)
    assert resp.status_code == 204
    assert await db_session.get(Product, prod_id) is None

@pytest.mark.asyncio
async def test_weight_and_settings_sync(client, auth_headers, db_session):
    """Test that logging weight updates user settings."""
    # 1. Log weight
    resp = await client.post("/api/weight", headers=auth_headers, json={"weight": 75.5})
    assert resp.status_code == 201
    assert resp.json()["weight"] == 75.5
    
    # 2. Verify settings updated
    settings = (await db_session.execute(select(UserSettings).where(UserSettings.user_id == 111))).scalar_one()
    assert settings.weight == 75.5
    
    # 3. Verify history
    resp = await client.get("/api/weight", headers=auth_headers)
    assert len(resp.json()) == 1
    assert resp.json()[0]["weight"] == 75.5

@pytest.mark.asyncio
async def test_smart_analyze_endpoint(client, auth_headers):
    """Test AI-powered food analysis mocking the service."""
    mock_result = {
        "name": "Big Mac",
        "calories": 550,
        "protein": 25,
        "fat": 30,
        "carbs": 45,
        "fiber": 3,
        "weight_grams": 215
    }
    
    with patch("services.normalization.NormalizationService.analyze_food_intake", new_callable=AsyncMock) as mock_analyze:
        mock_analyze.return_value = mock_result
        
        resp = await client.post("/api/smart/analyze", headers=auth_headers, json={"text": "A huge burger"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Big Mac"
        assert data["calories"] == 550
        assert data["weight_g"] == 215

@pytest.mark.asyncio
async def test_search_fridge_with_ai(client, auth_headers, db_session):
    """Test fridge search and AI summary mocking."""
    # Add some items
    db_session.add(Product(user_id=111, name="Eggs", price=10, quantity=10, category="Dairy", calories=150, source="test"))
    await db_session.commit()
    
    mock_summary = {"summary": "You have eggs. You can make an omelette.", "tags": [{"tag": "Eggs", "emoji": "🥚"}]}
    
    with patch("services.ai_brain.AIBrainService.summarize_fridge", new_callable=AsyncMock) as mock_ai:
        mock_ai.return_value = mock_summary
        
        # Test search
        resp = await client.get("/api/search/fridge?with_summary=true", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()["results"]) >= 1
        assert resp.json()["summary"] == mock_summary["summary"]

@pytest.mark.asyncio
async def test_water_logging_and_filtering(client, auth_headers):
    """Test water tracking with date filters."""
    # 1. Log water for today
    await client.post("/api/water", headers=auth_headers, json={"amount_ml": 200})
    
    # 2. Get today's list
    resp = await client.get("/api/water", headers=auth_headers)
    assert len(resp.json()) == 1
    
    # 3. Try to get water for future date
    future_date = (datetime.now(MSK_TZ) + timedelta(days=5)).date().isoformat()
    resp = await client.get(f"/api/water?date={future_date}", headers=auth_headers)
    assert len(resp.json()) == 0

@pytest.mark.asyncio
async def test_consumption_date_filtering(client, auth_headers, db_session):
    """Test consumption logs filtering by date range."""
    user_id = 111
    # Entry 1: 5 days ago
    past_date = datetime.now(MSK_TZ) - timedelta(days=5)
    db_session.add(ConsumptionLog(user_id=user_id, product_name="Old Cake", calories=500, date=past_date.replace(tzinfo=None)))
    # Entry 2: Today
    db_session.add(ConsumptionLog(user_id=user_id, product_name="New Apple", calories=50, date=datetime.now(MSK_TZ).replace(tzinfo=None)))
    await db_session.commit()
    
    # 1. Test target date
    today_str = datetime.now(MSK_TZ).date().isoformat()
    resp = await client.get(f"/api/consumption?date={today_str}", headers=auth_headers)
    assert len(resp.json()) == 1
    assert resp.json()[0]["product_name"] == "New Apple"
    
    # 2. Test range
    from_str = (datetime.now(MSK_TZ) - timedelta(days=6)).date().isoformat()
    resp = await client.get(f"/api/consumption?from={from_str}", headers=auth_headers)
    assert len(resp.json()) == 2

@pytest.mark.asyncio
async def test_daily_report_with_multiple_entries(client, auth_headers, db_session):
    """Test aggregate daily report calculation."""
    user_id = 111
    # Log 2 meals today
    db_session.add(ConsumptionLog(user_id=user_id, product_name="A", calories=100, protein=10, fat=5, carbs=20, date=datetime.now(MSK_TZ).replace(tzinfo=None)))
    db_session.add(ConsumptionLog(user_id=user_id, product_name="B", calories=250, protein=20, fat=10, carbs=30, date=datetime.now(MSK_TZ).replace(tzinfo=None)))
    
    # Log 1 water entry
    db_session.add(WaterLog(user_id=user_id, amount_ml=500, date=datetime.now(MSK_TZ).replace(tzinfo=None)))
    await db_session.commit()
    
    resp = await client.get("/api/reports/daily", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["calories_consumed"] == 350
    assert data["protein"] == 30
    assert data["meals_count"] == 2
