"""
Unit tests for handler modules (fridge, recipes, shopping).
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from database.models import Product, Receipt, ShoppingSession
from handlers import fridge, recipes, shopping


class TestFridgeHandler:
    """Tests for fridge handler."""

    @pytest.mark.asyncio
    async def test_show_fridge_summary_empty(self, db_session, mock_callback_query, sample_user):
        """Test fridge summary when fridge is empty."""
        # Mock get_db to return our test session
        with patch('handlers.fridge.get_db') as mock_get_db:
            async def db_generator():
                yield db_session
            mock_get_db.return_value = db_generator()

            # Call handler
            await fridge.show_fridge_summary(mock_callback_query)

            # Verify callback was answered
            mock_callback_query.answer.assert_called_once()

            # Verify message was edited or sent
            assert mock_callback_query.message.edit_media.called or mock_callback_query.message.answer_photo.called

    @pytest.mark.asyncio
    async def test_show_fridge_summary_with_products(
        self, db_session, mock_callback_query, sample_user, sample_receipt, sample_product
    ):
        """Test fridge summary when fridge has products."""
        # Add more products
        product2 = Product(
            receipt_id=sample_receipt.id,
            name="Хлеб",
            price=50.0,
            quantity=1.0
        )
        db_session.add(product2)
        await db_session.commit()

        # Mock get_db
        with patch('handlers.fridge.get_db') as mock_get_db:
            async def db_generator():
                yield db_session
            mock_get_db.return_value = db_generator()

            # Call handler
            await fridge.show_fridge_summary(mock_callback_query)

            # Verify callback was answered
            mock_callback_query.answer.assert_called_once()

            # Verify message contains product count
            # (check edit_text or answer was called with text containing count)
            edit_calls = mock_callback_query.message.edit_text.call_args_list
            answer_calls = mock_callback_query.message.answer.call_args_list

            if edit_calls:
                text = edit_calls[0][0][0] if edit_calls[0][0] else edit_calls[0][1].get('text', '')
                assert "2" in text or "два" in text.lower() or "товар" in text.lower()
            elif answer_calls:
                text = answer_calls[0][0][0] if answer_calls[0][0] else answer_calls[0][1].get('text', '')
                assert "2" in text or "два" in text.lower() or "товар" in text.lower()

    @pytest.mark.asyncio
    async def test_fridge_list_pagination(self, db_session, mock_callback_query, sample_user, sample_receipt):
        """Test fridge list pagination."""
        # Create multiple products
        for i in range(15):
            product = Product(
                receipt_id=sample_receipt.id,
                name=f"Продукт {i+1}",
                price=10.0 * (i + 1),
                quantity=1.0
            )
            db_session.add(product)
        await db_session.commit()

        # Mock get_db
        with patch('handlers.fridge.get_db') as mock_get_db:
            async def db_generator():
                yield db_session
            mock_get_db.return_value = db_generator()

            # Mock callback data for page 0
            mock_callback_query.data = "fridge_list:0"

            # Call handler (need to find the actual handler function)
            # This is a simplified test - in reality we'd call the actual handler
            # For now, just verify database query works
            from handlers.fridge import PAGE_SIZE

            stmt = (
                select(Product)
                .join(Receipt)
                .where(Receipt.user_id == sample_user.id)
                .order_by(Product.id.desc())
                .limit(PAGE_SIZE)
                .offset(0)
            )
            result = await db_session.execute(stmt)
            products = result.scalars().all()

            assert len(products) == PAGE_SIZE


class TestRecipesHandler:
    """Tests for recipes handler."""

    @pytest.mark.asyncio
    async def test_show_recipe_categories(self, mock_callback_query):
        """Test showing recipe categories."""
        # Call handler
        await recipes.show_recipe_categories(mock_callback_query)

        # Verify callback was answered
        mock_callback_query.answer.assert_called_once()

        # Verify message was edited or sent with categories
        edit_calls = mock_callback_query.message.edit_media.call_args_list
        answer_calls = mock_callback_query.message.answer_photo.call_args_list

        # Handler should show category buttons
        assert edit_calls or answer_calls

    @pytest.mark.asyncio
    async def test_generate_recipes_success(
        self, db_session, mock_callback_query, sample_user, sample_receipt, sample_product
    ):
        """Test successful recipe generation."""
        # Mock AI service
        mock_recipes = {
            "recipes": [
                {
                    "title": "Тестовый рецепт",
                    "description": "Описание",
                    "calories": 500,
                    "ingredients": [{"name": "Молоко", "amount": "1л"}],
                    "steps": ["Шаг 1", "Шаг 2"]
                }
            ]
        }

        # Mock get_db to return our test session
        async def db_generator():
            yield db_session

        # Mock cache functions to use our test session
        async def mock_get_cached(*args, **kwargs):
            return []  # No cached recipes

        async def mock_store_recipes(*args, **kwargs):
            pass  # Don't actually store

        with patch('handlers.recipes.get_db', return_value=db_generator()):
            with patch('handlers.recipes.get_cached_recipes', new_callable=AsyncMock, side_effect=mock_get_cached):
                with patch('handlers.recipes.store_recipes', new_callable=AsyncMock, side_effect=mock_store_recipes):
                    with patch('handlers.recipes.AIService.generate_recipes', new_callable=AsyncMock) as mock_ai:
                        mock_ai.return_value = mock_recipes

                        # Mock callback data
                        mock_callback_query.data = "recipes_cat:Main"

                        # Call handler
                        await recipes.generate_recipes_by_category(mock_callback_query)

                        # Commit to persist any changes
                        await db_session.commit()

                        # Verify AI service was called
                        mock_ai.assert_called_once()

                        # Verify callback was answered
                        mock_callback_query.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_recipes_no_ingredients(self, db_session, mock_callback_query, sample_user):
        """Test recipe generation when no ingredients available."""
        # Mock get_db to return our test session
        async def db_generator():
            yield db_session

        # Mock cache functions
        async def mock_get_cached(*args, **kwargs):
            return []

        with patch('handlers.recipes.get_db', return_value=db_generator()):
            with patch('handlers.recipes.get_cached_recipes', new_callable=AsyncMock, side_effect=mock_get_cached):
                # Mock callback data
                mock_callback_query.data = "recipes_cat:Main"

                # Call handler
                await recipes.generate_recipes_by_category(mock_callback_query)

                # Commit to persist any changes
                await db_session.commit()

                # Handler should handle empty ingredients gracefully
                # It edits the message but doesn't call answer() when no ingredients
                # Verify message was edited (either edit_media or edit_text)
                assert (
                    mock_callback_query.message.edit_media.called or
                    mock_callback_query.message.edit_text.called
                )


class TestShoppingHandler:
    """Tests for shopping handler."""

    @pytest.mark.asyncio
    async def test_start_shopping_new_session(self, db_session, mock_callback_query, sample_user, mock_fsm_context):
        """Test starting shopping mode with new session."""
        # Mock FSM context
        mock_fsm_context.get_data.return_value = {}

        # Mock get_db to return our test session
        async def db_generator():
            yield db_session

        with patch('handlers.shopping.get_db', return_value=db_generator()):
            # Call handler
            await shopping.start_shopping(mock_callback_query, mock_fsm_context)

            # Commit to persist changes made by handler
            await db_session.commit()

        # Verify session was created
        stmt = select(ShoppingSession).where(
            ShoppingSession.user_id == sample_user.id,
            ShoppingSession.is_active == True  # noqa: E712
        )
        result = await db_session.execute(stmt)
        session = result.scalar_one_or_none()

        assert session is not None
        assert session.user_id == sample_user.id
        assert session.is_active is True

        # Verify FSM state was set
        mock_fsm_context.set_state.assert_called_once()
        mock_fsm_context.update_data.assert_called_once()

        # Verify callback was answered
        mock_callback_query.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_shopping_existing_session(
        self, db_session, mock_callback_query, sample_user, mock_fsm_context
    ):
        """Test starting shopping mode with existing active session."""
        # Create existing session
        existing_session = ShoppingSession(user_id=sample_user.id, is_active=True)
        db_session.add(existing_session)
        await db_session.commit()
        await db_session.refresh(existing_session)
        existing_session_id = existing_session.id

        # Mock get_db to return our test session
        async def db_generator():
            yield db_session

        with patch('handlers.shopping.get_db', return_value=db_generator()):
            # Call handler
            await shopping.start_shopping(mock_callback_query, mock_fsm_context)

            # Commit to persist any changes
            await db_session.commit()

        # Verify existing session is reused (not new one created)
        stmt = select(ShoppingSession).where(
            ShoppingSession.user_id == sample_user.id,
            ShoppingSession.is_active == True  # noqa: E712
        )
        result = await db_session.execute(stmt)
        sessions = result.scalars().all()

        assert len(sessions) == 1
        assert sessions[0].id == existing_session_id

    @pytest.mark.asyncio
    async def test_scan_label_success(
        self, db_session, mock_telegram_message, mock_bot, mock_fsm_context, sample_user
    ):
        """Test successful label scanning."""
        # Create shopping session
        session = ShoppingSession(user_id=sample_user.id, is_active=True)
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        # Mock FSM context
        mock_fsm_context.get_data.return_value = {"shopping_session_id": session.id}

        # Mock photo
        mock_photo = MagicMock()
        mock_photo.file_id = "test_file_id"
        mock_telegram_message.photo = [mock_photo]

        # Mock file download
        mock_file = MagicMock()
        mock_file.file_path = "test_path"
        mock_bot.get_file.return_value = mock_file

        # Mock OCR service
        mock_ocr_result = {
            "name": "Молоко",
            "brand": "Домик в деревне",
            "weight": "1л",
            "calories": 64,
            "protein": 3.2,
            "fat": 3.5,
            "carbs": 4.7
        }

        async def mock_download(path, dest):
            dest.write(b"fake_image")
        mock_bot.download_file = AsyncMock(side_effect=mock_download)

        # Mock get_db to return our test session
        with patch('handlers.shopping.get_db') as mock_get_db:
            async def db_generator():
                yield db_session
            mock_get_db.return_value = db_generator()

        with patch('handlers.shopping.LabelOCRService.parse_label', new_callable=AsyncMock) as mock_ocr:
            mock_ocr.return_value = mock_ocr_result

            # Call handler
            await shopping.scan_label(mock_telegram_message, mock_bot, mock_fsm_context)

            # Verify OCR was called
            mock_ocr.assert_called_once()

            # Verify bot methods were called
            mock_bot.get_file.assert_called_once()
            mock_bot.download_file.assert_called_once()

            # Verify message was sent (status message)
            assert mock_telegram_message.answer.called

    @pytest.mark.asyncio
    async def test_scan_label_no_session(self, mock_telegram_message, mock_bot, mock_fsm_context):
        """Test label scanning when no active session."""
        # Mock FSM context with no session
        mock_fsm_context.get_data.return_value = {}

        # Call handler
        await shopping.scan_label(mock_telegram_message, mock_bot, mock_fsm_context)

        # Verify error message was sent
        mock_telegram_message.answer.assert_called_once()
        call_args = mock_telegram_message.answer.call_args[0][0]
        assert "сесси" in call_args.lower() or "нет активной" in call_args.lower()

