"""Tests for consultant service."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from database.models import Product, UserSettings
from services.consultant import ConsultantService


@pytest.mark.asyncio
async def test_analyze_product_not_initialized(sample_product, db_session):
    """Test that consultant returns empty recommendations for non-initialized user."""
    settings = UserSettings(user_id=123456789, is_initialized=False)
    db_session.add(settings)
    await db_session.commit()

    result = await ConsultantService.analyze_product(sample_product, settings, context="receipt")

    assert result == {"warnings": [], "recommendations": [], "missing": []}


@pytest.mark.asyncio
async def test_analyze_product_initialized_user(sample_product, sample_user_settings):
    """Test consultant analysis for initialized user."""
    # Mock AI response
    mock_ai_response = {
        "warnings": ["⚠️ Высокая калорийность для похудения"],
        "recommendations": ["✅ Хороший источник белка"],
        "missing": [],
    }

    with patch.object(
        ConsultantService, "_generate_ai_recommendation", return_value=mock_ai_response
    ):
        result = await ConsultantService.analyze_product(
            sample_product, sample_user_settings, context="receipt"
        )

        assert "warnings" in result
        assert "recommendations" in result
        assert "missing" in result
        assert len(result["warnings"]) > 0


@pytest.mark.asyncio
async def test_analyze_product_ai_fallback(sample_product, sample_user_settings):
    """Test that consultant falls back to simple rules if AI fails."""
    # Mock AI to return None (failure)
    with patch.object(ConsultantService, "_generate_ai_recommendation", return_value=None):
        result = await ConsultantService.analyze_product(
            sample_product, sample_user_settings, context="receipt"
        )

        # Should use simple rules fallback
        assert "warnings" in result
        assert "recommendations" in result
        assert "missing" in result


@pytest.mark.asyncio
async def test_analyze_products_multiple(sample_user_settings, db_session):
    """Test analyzing multiple products."""
    # Create multiple products
    products = [
        Product(name="Шоколад", calories=500, protein=5, fat=30, carbs=50, price=100, quantity=1),
        Product(name="Яблоко", calories=50, protein=0.5, fat=0.2, carbs=12, price=50, quantity=1),
    ]

    # Mock AI response
    mock_ai_response = {
        "warnings": ["⚠️ Высокая калорийность"],
        "recommendations": ["✅ Полезный продукт"],
        "missing": [],
    }

    with patch.object(
        ConsultantService, "analyze_product", return_value=mock_ai_response
    ):
        result = await ConsultantService.analyze_products(
            products, sample_user_settings, context="receipt"
        )

        assert "warnings" in result
        assert "recommendations" in result
        assert "missing" in result


@pytest.mark.asyncio
async def test_analyze_products_empty_list(sample_user_settings):
    """Test analyzing empty product list."""
    result = await ConsultantService.analyze_products([], sample_user_settings, context="receipt")

    assert result == {"warnings": [], "recommendations": [], "missing": []}


@pytest.mark.asyncio
async def test_simple_recommendations_allergy_check(sample_user_settings):
    """Test simple recommendations check for allergies."""
    product = Product(
        name="Молоко с орехами",
        calories=100,
        protein=3,
        fat=3,
        carbs=5,
        price=100,
        quantity=1,
    )
    sample_user_settings.allergies = "орехи"

    result = ConsultantService._calculate_simple_recommendations(product, sample_user_settings)

    assert len(result["warnings"]) > 0
    assert any("аллергия" in w.lower() or "орех" in w.lower() for w in result["warnings"])


@pytest.mark.asyncio
async def test_simple_recommendations_lose_weight_goal(sample_user_settings):
    """Test simple recommendations for lose_weight goal."""
    product = Product(
        name="Высококалорийный продукт",
        calories=500,
        protein=10,
        fat=20,
        carbs=50,
        price=100,
        quantity=1,
    )
    sample_user_settings.goal = "lose_weight"

    result = ConsultantService._calculate_simple_recommendations(product, sample_user_settings)

    # Should have warning about high calories
    assert len(result["warnings"]) > 0
    assert any("калорий" in w.lower() for w in result["warnings"])


@pytest.mark.asyncio
async def test_simple_recommendations_gain_mass_goal(sample_user_settings):
    """Test simple recommendations for gain_mass goal."""
    product = Product(
        name="Низкокалорийный продукт",
        calories=100,
        protein=5,
        fat=2,
        carbs=15,
        price=100,
        quantity=1,
    )
    sample_user_settings.goal = "gain_mass"

    result = ConsultantService._calculate_simple_recommendations(product, sample_user_settings)

    # Should have suggestion about needing more calories
    assert len(result["missing"]) > 0 or len(result["warnings"]) > 0


@pytest.mark.asyncio
async def test_simple_recommendations_high_protein(sample_user_settings):
    """Test simple recommendations for high protein products."""
    product = Product(
        name="Высокобелковый продукт",
        calories=200,
        protein=25,
        fat=5,
        carbs=10,
        price=100,
        quantity=1,
    )

    result = ConsultantService._calculate_simple_recommendations(product, sample_user_settings)

    # Should have positive recommendation about protein
    assert len(result["recommendations"]) > 0
    assert any("белк" in r.lower() for r in result["recommendations"])









