"""
Unit tests for service modules (OCRService, NormalizationService).
"""

import pytest

from services.normalization import NormalizationService
from services.ocr import OCRService


class TestOCRService:
    """Tests for OCRService."""

    @pytest.mark.asyncio
    async def test_parse_receipt_success(self, aioresp, mock_openrouter_response):
        """Test successful receipt parsing."""
        # Mock successful API response
        aioresp.post(
            "https://openrouter.ai/api/v1/chat/completions",
            payload=mock_openrouter_response
        )

        # Create test image bytes
        image_bytes = b"fake_image_data"

        # Call the service
        result = await OCRService.parse_receipt(image_bytes)

        # Verify result
        assert result is not None
        assert "items" in result
        assert len(result["items"]) > 0
        assert result["items"][0]["name"] == "Молоко"
        assert result["items"][0]["price"] == 100.0

    @pytest.mark.asyncio
    async def test_parse_receipt_all_models_fail(self, aioresp, mock_openrouter_error_response):
        """Test that exception is raised when all models fail."""
        # Mock all models failing
        for _ in OCRService.MODELS:
            aioresp.post(
                "https://openrouter.ai/api/v1/chat/completions",
                payload=mock_openrouter_error_response,
                status=500
            )

        image_bytes = b"fake_image_data"

        # Verify exception is raised
        with pytest.raises(Exception, match="All OCR models failed"):
            await OCRService.parse_receipt(image_bytes)

    @pytest.mark.asyncio
    async def test_parse_receipt_retry_logic(self, aioresp, mock_openrouter_response):
        """Test that retry logic works correctly."""
        # Mock first attempt failing, second succeeding
        aioresp.post(
            "https://openrouter.ai/api/v1/chat/completions",
            status=500
        )
        aioresp.post(
            "https://openrouter.ai/api/v1/chat/completions",
            payload=mock_openrouter_response
        )

        image_bytes = b"fake_image_data"

        # Call the service (should retry and succeed)
        result = await OCRService.parse_receipt(image_bytes)

        # Verify result
        assert result is not None
        assert "items" in result

    @pytest.mark.asyncio
    async def test_parse_receipt_invalid_json(self, aioresp):
        """Test handling of invalid JSON response."""
        # Mock API returning invalid JSON
        invalid_response = {
            "choices": [
                {
                    "message": {
                        "content": "This is not valid JSON {"
                    }
                }
            ]
        }

        aioresp.post(
            "https://openrouter.ai/api/v1/chat/completions",
            payload=invalid_response
        )

        # Mock remaining models to fail
        for _ in OCRService.MODELS[1:]:
            aioresp.post(
                "https://openrouter.ai/api/v1/chat/completions",
                status=500
            )

        image_bytes = b"fake_image_data"

        # Should raise exception after all models fail
        with pytest.raises(Exception):
            await OCRService.parse_receipt(image_bytes)

    @pytest.mark.asyncio
    async def test_parse_receipt_empty_items(self, aioresp):
        """Test handling of empty items list."""
        empty_response = {
            "choices": [
                {
                    "message": {
                        "content": '{"items": [], "total": 0.0}'
                    }
                }
            ]
        }

        aioresp.post(
            "https://openrouter.ai/api/v1/chat/completions",
            payload=empty_response
        )

        image_bytes = b"fake_image_data"

        result = await OCRService.parse_receipt(image_bytes)

        assert result is not None
        assert "items" in result
        assert len(result["items"]) == 0
        assert result["total"] == 0.0


class TestNormalizationService:
    """Tests for NormalizationService."""

    @pytest.mark.asyncio
    async def test_normalize_products_success(self, aioresp, mock_normalization_response):
        """Test successful product normalization."""
        # Mock successful API response
        aioresp.post(
            "https://openrouter.ai/api/v1/chat/completions",
            payload=mock_normalization_response
        )

        raw_items = [
            {"name": "Молоко", "price": 100.0, "quantity": 1.0}
        ]

        result = await NormalizationService.normalize_products(raw_items)

        assert result is not None
        assert len(result) == 1
        assert result[0]["name"] == "Молоко 1л"
        assert result[0]["category"] == "Молочные продукты"
        assert result[0]["calories"] == 64
        assert result[0]["price"] == 100.0  # Original price preserved

    @pytest.mark.asyncio
    async def test_normalize_products_empty_list(self):
        """Test that empty list returns empty list."""
        result = await NormalizationService.normalize_products([])

        assert result == []

    @pytest.mark.asyncio
    async def test_normalize_products_all_models_fail(self, aioresp):
        """Test that raw items are returned when all models fail."""
        # Mock all models failing
        for _ in NormalizationService.MODELS:
            aioresp.post(
                "https://openrouter.ai/api/v1/chat/completions",
                status=500
            )

        raw_items = [
            {"name": "Молоко", "price": 100.0, "quantity": 1.0}
        ]

        result = await NormalizationService.normalize_products(raw_items)

        # Should return raw items as fallback
        assert result is not None
        assert len(result) == 1
        assert result[0]["name"] == "Молоко"  # Original name preserved
        assert result[0]["price"] == 100.0

    @pytest.mark.asyncio
    async def test_normalize_products_partial_match(self, aioresp):
        """Test normalization with partial matches."""
        partial_response = {
            "choices": [
                {
                    "message": {
                        "content": '{"normalized": [{"original": "Молоко", "name": "Молоко 1л", "category": "Молочные продукты", "calories": 64}]}'
                    }
                }
            ]
        }

        aioresp.post(
            "https://openrouter.ai/api/v1/chat/completions",
            payload=partial_response
        )

        raw_items = [
            {"name": "Молоко", "price": 100.0, "quantity": 1.0},
            {"name": "Хлеб", "price": 50.0, "quantity": 1.0}  # Not in normalized response
        ]

        result = await NormalizationService.normalize_products(raw_items)

        assert len(result) == 2
        # First item should be normalized
        assert result[0]["name"] == "Молоко 1л"
        assert result[0]["category"] == "Молочные продукты"
        # Second item should fallback to raw name
        assert result[1]["name"] == "Хлеб"
        assert result[1]["category"] == "Uncategorized"

    @pytest.mark.asyncio
    async def test_normalize_products_invalid_json(self, aioresp):
        """Test handling of invalid JSON response."""
        invalid_response = {
            "choices": [
                {
                    "message": {
                        "content": "This is not valid JSON {"
                    }
                }
            ]
        }

        # Mock first model returning invalid JSON, others failing
        aioresp.post(
            "https://openrouter.ai/api/v1/chat/completions",
            payload=invalid_response
        )

        for _ in NormalizationService.MODELS[1:]:
            aioresp.post(
                "https://openrouter.ai/api/v1/chat/completions",
                status=500
            )

        raw_items = [
            {"name": "Молоко", "price": 100.0, "quantity": 1.0}
        ]

        # Should return raw items as fallback
        result = await NormalizationService.normalize_products(raw_items)

        assert result is not None
        assert len(result) == 1
        assert result[0]["name"] == "Молоко"



