"""Additional unit tests for service modules (matching, price_search, price_tag_ocr)."""
from unittest.mock import patch

import pytest

from database.models import LabelScan, ShoppingSession
from services.matching import MatchingService
from services.price_search import PriceSearchService
from services.price_tag_ocr import PriceTagOCRService


class TestMatchingService:
    """Tests for MatchingService."""

    @pytest.mark.asyncio
    async def test_match_products_success(
        self, db_session, sample_user, sample_receipt, sample_product
    ):
        """Test successful product-label matching."""
        # Create shopping session
        session = ShoppingSession(user_id=sample_user.id)
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        # Create label scan
        label = LabelScan(
            session_id=session.id,
            name="Молоко",
            brand="Домик в деревне",
            weight="1л",
            calories=64.0,
            protein=3.0,
            fat=3.2,
            carbs=4.7
        )
        db_session.add(label)
        await db_session.commit()
        await db_session.refresh(label)

        with patch('services.matching.get_db') as mock_get_db:
            async def db_generator():
                yield db_session
            mock_get_db.return_value = db_generator()

            result = await MatchingService.match_products([sample_product.id], session.id)

            assert result is not None
            assert len(result["matched"]) == 1
            assert result["matched"][0]["product_id"] == sample_product.id
            assert result["matched"][0]["label_id"] == label.id
            assert result["matched"][0]["score"] >= 70

            # Verify product nutrition was updated
            await db_session.refresh(sample_product)
            assert sample_product.calories == 64.0
            assert sample_product.protein == 3.0

    @pytest.mark.asyncio
    async def test_match_products_no_labels(
        self, db_session, sample_user, sample_receipt, sample_product
    ):
        """Test matching when no labels exist."""
        session = ShoppingSession(user_id=sample_user.id)
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        with patch('services.matching.get_db') as mock_get_db:
            async def db_generator():
                yield db_session
            mock_get_db.return_value = db_generator()

            result = await MatchingService.match_products([sample_product.id], session.id)

            assert result is None

    @pytest.mark.asyncio
    async def test_match_products_no_match(
        self, db_session, sample_user, sample_receipt, sample_product
    ):
        """Test matching when no products match labels."""
        session = ShoppingSession(user_id=sample_user.id)
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        # Create label with very different name
        label = LabelScan(
            session_id=session.id,
            name="Совершенно другой товар",
            brand=None,
            weight=None
        )
        db_session.add(label)
        await db_session.commit()

        with patch('services.matching.get_db') as mock_get_db:
            async def db_generator():
                yield db_session
            mock_get_db.return_value = db_generator()

            result = await MatchingService.match_products([sample_product.id], session.id)

            assert result is not None
            assert len(result["matched"]) == 0
            assert len(result["unmatched_products"]) == 1
            assert len(result["unmatched_labels"]) == 1

    @pytest.mark.asyncio
    async def test_match_products_invalid_session(
        self, db_session, sample_product
    ):
        """Test matching with invalid session ID."""
        with patch('services.matching.get_db') as mock_get_db:
            async def db_generator():
                yield db_session
            mock_get_db.return_value = db_generator()

            result = await MatchingService.match_products([sample_product.id], 99999)

            assert result is None

    @pytest.mark.asyncio
    async def test_match_products_empty_product_ids(self, db_session, sample_user):
        """Test matching with empty product IDs."""
        session = ShoppingSession(user_id=sample_user.id)
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        with patch('services.matching.get_db') as mock_get_db:
            async def db_generator():
                yield db_session
            mock_get_db.return_value = db_generator()

            result = await MatchingService.match_products([], session.id)

            assert result is None

    def test_similarity_with_brand_bonus(self):
        """Test similarity calculation with brand bonus."""
        label = LabelScan(
            session_id=1,
            name="Молоко",
            brand="Домик в деревне",
            weight=None
        )
        score = MatchingService._similarity("Молоко Домик в деревне", label)
        assert score > 70  # Should have bonus for brand match

    def test_similarity_with_weight_bonus(self):
        """Test similarity calculation with weight bonus."""
        label = LabelScan(
            session_id=1,
            name="Молоко",
            brand=None,
            weight="1л"
        )
        score = MatchingService._similarity("Молоко 1л", label)
        assert score > 70  # Should have bonus for weight match


class TestPriceSearchService:
    """Tests for PriceSearchService."""

    @pytest.mark.asyncio
    async def test_search_prices_success(self, aioresp):
        """Test successful price search."""
        mock_response = {
            "choices": [
                {
                    "message": {
                        "content": '{"prices": [{"store": "Пятёрочка", "price": 89.99}, {"store": "Магнит", "price": 92.50}]}'
                    }
                }
            ]
        }

        aioresp.post(
            "https://openrouter.ai/api/v1/chat/completions",
            payload=mock_response
        )

        result = await PriceSearchService.search_prices("Молоко 3.2%")

        assert result is not None
        assert result["product"] == "Молоко 3.2%"
        assert len(result["prices"]) == 2
        assert result["min_price"] == 89.99
        assert result["max_price"] == 92.50
        assert result["avg_price"] == (89.99 + 92.50) / 2

    @pytest.mark.asyncio
    async def test_search_prices_no_prices(self, aioresp):
        """Test price search when no prices found."""
        mock_response = {
            "choices": [
                {
                    "message": {
                        "content": '{"prices": []}'
                    }
                }
            ]
        }

        aioresp.post(
            "https://openrouter.ai/api/v1/chat/completions",
            payload=mock_response
        )

        result = await PriceSearchService.search_prices("Редкий товар")

        assert result is None

    @pytest.mark.asyncio
    async def test_search_prices_json_parse_error(self, aioresp):
        """Test price search with JSON parse error."""
        mock_response = {
            "choices": [
                {
                    "message": {
                        "content": "This is not JSON, but some text response"
                    }
                }
            ]
        }

        aioresp.post(
            "https://openrouter.ai/api/v1/chat/completions",
            payload=mock_response
        )

        result = await PriceSearchService.search_prices("Товар")

        # Should return raw_response if JSON parsing fails
        assert result is not None
        assert "raw_response" in result

    @pytest.mark.asyncio
    async def test_search_prices_api_error(self, aioresp):
        """Test price search when API returns error."""
        aioresp.post(
            "https://openrouter.ai/api/v1/chat/completions",
            status=500
        )

        result = await PriceSearchService.search_prices("Товар")

        # Should retry 3 times, then return None
        assert result is None


class TestPriceTagOCRService:
    """Tests for PriceTagOCRService."""

    @pytest.mark.asyncio
    async def test_parse_price_tag_success(self, aioresp):
        """Test successful price tag parsing."""
        mock_response = {
            "choices": [
                {
                    "message": {
                        "content": '{"product_name": "Молоко", "volume": "1л", "price": 89.99, "store": "Пятёрочка", "date": "2024-11-26"}'
                    }
                }
            ]
        }

        aioresp.post(
            "https://openrouter.ai/api/v1/chat/completions",
            payload=mock_response
        )

        image_bytes = b"fake_image_data"
        result = await PriceTagOCRService.parse_price_tag(image_bytes)

        assert result is not None
        assert result["product_name"] == "Молоко"
        assert result["volume"] == "1л"
        assert result["price"] == 89.99
        assert result["store"] == "Пятёрочка"
        assert result["date"] == "2024-11-26"

    @pytest.mark.asyncio
    async def test_parse_price_tag_all_models_fail(self, aioresp):
        """Test price tag parsing when all models fail."""
        # Mock all models failing
        for _ in PriceTagOCRService.MODELS:
            aioresp.post(
                "https://openrouter.ai/api/v1/chat/completions",
                status=500
            )

        image_bytes = b"fake_image_data"
        result = await PriceTagOCRService.parse_price_tag(image_bytes)

        assert result is None

    @pytest.mark.asyncio
    async def test_parse_price_tag_json_with_markdown(self, aioresp):
        """Test price tag parsing with markdown-wrapped JSON."""
        mock_response = {
            "choices": [
                {
                    "message": {
                        "content": '```json\n{"product_name": "Хлеб", "price": 50.0}\n```'
                    }
                }
            ]
        }

        aioresp.post(
            "https://openrouter.ai/api/v1/chat/completions",
            payload=mock_response
        )

        image_bytes = b"fake_image_data"
        result = await PriceTagOCRService.parse_price_tag(image_bytes)

        assert result is not None
        assert result["product_name"] == "Хлеб"
        assert result["price"] == 50.0

    @pytest.mark.asyncio
    async def test_parse_price_tag_partial_data(self, aioresp):
        """Test price tag parsing with partial data."""
        mock_response = {
            "choices": [
                {
                    "message": {
                        "content": '{"product_name": "Товар", "price": 100.0, "volume": null, "store": null, "date": null}'
                    }
                }
            ]
        }

        aioresp.post(
            "https://openrouter.ai/api/v1/chat/completions",
            payload=mock_response
        )

        image_bytes = b"fake_image_data"
        result = await PriceTagOCRService.parse_price_tag(image_bytes)

        assert result is not None
        assert result["product_name"] == "Товар"
        assert result["price"] == 100.0
        assert result["volume"] is None
        assert result["store"] is None

