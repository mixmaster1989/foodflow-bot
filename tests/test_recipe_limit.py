import pytest
from httpx import AsyncClient, ASGITransport
from datetime import datetime, date

from api.main import app
from database.base import get_db
from database.models import User, UserSettings

@pytest.fixture(scope="function")
async def client(db_session):
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_logic_step_by_step(db_session):
    # Let's test the router logic directly or mock AIService
    from api.routers.recipes import generate_recipes
    from api.schemas import RecipeRequest
    from unittest.mock import patch, AsyncMock
    from fastapi import HTTPException
    
    user = User(id=777)
    db_session.add(user)
    await db_session.commit()
    
    with patch("services.ai.AIService.generate_recipes", new_callable=AsyncMock) as mock_ai:
        mock_ai.return_value = {"recipes": []}
        
        # Call 1 (Refresh)
        await generate_recipes(RecipeRequest(category="Breakfast", refresh=True), user, db_session)
        
        from sqlalchemy import select
        settings = (await db_session.execute(select(UserSettings).where(UserSettings.user_id == 777))).scalar_one()
        assert settings.recipe_refresh_count == 1
        assert settings.last_recipe_refresh_date == date.today().isoformat()
        
        # Call 2
        await generate_recipes(RecipeRequest(category="Breakfast", refresh=True), user, db_session)
        assert settings.recipe_refresh_count == 2
        
        # Call 3
        await generate_recipes(RecipeRequest(category="Breakfast", refresh=True), user, db_session)
        assert settings.recipe_refresh_count == 3
        
        # Call 4 - Should raise HTTPException
        with pytest.raises(HTTPException) as exc:
            await generate_recipes(RecipeRequest(category="Breakfast", refresh=True), user, db_session)
        assert exc.value.status_code == 429
        assert "Лимит обновлений" in exc.value.detail
