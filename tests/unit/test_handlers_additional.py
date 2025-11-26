"""Additional unit tests for handler modules (common, correction, stats, shopping_list, user_settings)."""
from unittest.mock import AsyncMock, patch

import pytest

from database.models import (
    ConsumptionLog,
    ShoppingListItem,
    User,
    UserSettings,
)
from handlers import common, correction, shopping_list, stats, user_settings


class TestCommonHandler:
    """Tests for common handler."""

    @pytest.mark.asyncio
    async def test_cmd_start_new_user(self, db_session, mock_telegram_message, mock_telegram_user):
        """Test /start command with new user."""
        with patch('handlers.common.get_db') as mock_get_db:
            async def db_generator():
                yield db_session
            mock_get_db.return_value = db_generator()

            with patch('handlers.common.show_main_menu') as mock_show_menu:
                await common.cmd_start(mock_telegram_message)

                # Verify user was created
                from sqlalchemy import select
                stmt = select(User).where(User.id == mock_telegram_user.id)
                result = await db_session.execute(stmt)
                user = result.scalar_one_or_none()
                assert user is not None
                assert user.id == mock_telegram_user.id

                # Verify main menu was shown
                mock_show_menu.assert_called_once()

    @pytest.mark.asyncio
    async def test_cmd_start_existing_user(self, db_session, mock_telegram_message, sample_user):
        """Test /start command with existing user."""
        with patch('handlers.common.get_db') as mock_get_db:
            async def db_generator():
                yield db_session
            mock_get_db.return_value = db_generator()

            with patch('handlers.common.show_main_menu') as mock_show_menu:
                await common.cmd_start(mock_telegram_message)

                # Verify main menu was shown
                mock_show_menu.assert_called_once()


class TestCorrectionHandler:
    """Tests for correction handler."""

    @pytest.mark.asyncio
    async def test_start_correction_success(
        self, db_session, mock_callback_query, sample_product
    ):
        """Test starting correction for existing product."""
        mock_callback_query.data = f"correct_{sample_product.id}"

        with patch('handlers.correction.get_db') as mock_get_db:
            async def db_generator():
                yield db_session
            mock_get_db.return_value = db_generator()

            await correction.start_correction(mock_callback_query, AsyncMock())

            # Verify callback was answered
            mock_callback_query.answer.assert_called_once()
            # Verify message was sent
            mock_callback_query.message.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_correction_product_not_found(self, db_session, mock_callback_query):
        """Test starting correction for non-existent product."""
        mock_callback_query.data = "correct_99999"

        with patch('handlers.correction.get_db') as mock_get_db:
            async def db_generator():
                yield db_session
            mock_get_db.return_value = db_generator()

            await correction.start_correction(mock_callback_query, AsyncMock())

            # Verify error answer
            mock_callback_query.answer.assert_called_once_with(
                "❌ Продукт не найден", show_alert=True
            )

    @pytest.mark.asyncio
    async def test_apply_correction_success(
        self, db_session, mock_telegram_message, sample_product
    ):
        """Test applying correction to product."""
        mock_telegram_message.text = "Новое название"

        mock_state = AsyncMock()
        mock_state.get_data = AsyncMock(return_value={"product_id": sample_product.id})
        mock_state.clear = AsyncMock()

        with patch('handlers.correction.get_db') as mock_get_db:
            async def db_generator():
                yield db_session
            mock_get_db.return_value = db_generator()

            await correction.apply_correction(mock_telegram_message, mock_state)

            # Verify product was updated
            await db_session.refresh(sample_product)
            assert sample_product.name == "Новое название"

            # Verify state was cleared
            mock_state.clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_apply_correction_empty_name(
        self, db_session, mock_telegram_message, sample_product
    ):
        """Test applying correction with empty name."""
        mock_telegram_message.text = "   "

        mock_state = AsyncMock()
        mock_state.get_data = AsyncMock(return_value={"product_id": sample_product.id})

        with patch('handlers.correction.get_db') as mock_get_db:
            async def db_generator():
                yield db_session
            mock_get_db.return_value = db_generator()

            await correction.apply_correction(mock_telegram_message, mock_state)

            # Verify error message was sent
            mock_telegram_message.answer.assert_called_once_with(
                "❌ Название не может быть пустым"
            )


class TestStatsHandler:
    """Tests for stats handler."""

    @pytest.mark.asyncio
    async def test_show_stats_menu_empty(self, db_session, mock_callback_query, sample_user):
        """Test stats menu when no consumption logs exist."""
        with patch('handlers.stats.get_db') as mock_get_db:
            async def db_generator():
                yield db_session
            mock_get_db.return_value = db_generator()

            await stats.show_stats_menu(mock_callback_query)

            # Verify callback was answered
            mock_callback_query.answer.assert_called_once()
            # Verify message was edited or sent
            assert (
                mock_callback_query.message.edit_media.called
                or mock_callback_query.message.answer_photo.called
            )

    @pytest.mark.asyncio
    async def test_show_stats_menu_with_logs(
        self, db_session, mock_callback_query, sample_user
    ):
        """Test stats menu with consumption logs."""
        # Add consumption log
        log = ConsumptionLog(
            user_id=sample_user.id,
            product_name="Тест",
            calories=100.0,
            protein=10.0,
            fat=5.0,
            carbs=15.0
        )
        db_session.add(log)
        await db_session.commit()

        with patch('handlers.stats.get_db') as mock_get_db:
            async def db_generator():
                yield db_session
            mock_get_db.return_value = db_generator()

            await stats.show_stats_menu(mock_callback_query)

            # Verify callback was answered
            mock_callback_query.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_stats_placeholder(self, mock_callback_query):
        """Test stats placeholder handler."""
        await stats.stats_placeholder(mock_callback_query)

        # Verify alert was shown
        mock_callback_query.answer.assert_called_once_with(
            "Скоро будет доступно!", show_alert=True
        )


class TestShoppingListHandler:
    """Tests for shopping list handler."""

    @pytest.mark.asyncio
    async def test_show_shopping_list_empty(self, db_session, mock_callback_query, sample_user):
        """Test shopping list when empty."""
        with patch('handlers.shopping_list.get_db') as mock_get_db:
            async def db_generator():
                yield db_session
            mock_get_db.return_value = db_generator()

            await shopping_list.show_shopping_list(mock_callback_query)

            # Verify callback was answered
            mock_callback_query.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_show_shopping_list_with_items(
        self, db_session, mock_callback_query, sample_user
    ):
        """Test shopping list with items."""
        # Add shopping list items
        item1 = ShoppingListItem(
            user_id=sample_user.id,
            product_name="Молоко",
            is_bought=False
        )
        item2 = ShoppingListItem(
            user_id=sample_user.id,
            product_name="Хлеб",
            is_bought=True
        )
        db_session.add(item1)
        db_session.add(item2)
        await db_session.commit()

        with patch('handlers.shopping_list.get_db') as mock_get_db:
            async def db_generator():
                yield db_session
            mock_get_db.return_value = db_generator()

            await shopping_list.show_shopping_list(mock_callback_query)

            # Verify callback was answered
            mock_callback_query.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_add_item(self, mock_callback_query, mock_fsm_context):
        """Test starting add item flow."""
        await shopping_list.start_add_item(mock_callback_query, mock_fsm_context)

        # Verify state was set
        mock_fsm_context.set_state.assert_called_once()
        # Verify callback was answered
        mock_callback_query.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_item(self, db_session, mock_telegram_message, sample_user):
        """Test adding items to shopping list."""
        mock_telegram_message.text = "Молоко, Хлеб, Яйца"

        mock_state = AsyncMock()
        mock_state.clear = AsyncMock()

        with patch('handlers.shopping_list.get_db') as mock_get_db:
            async def db_generator():
                yield db_session
            mock_get_db.return_value = db_generator()

            await shopping_list.add_item(mock_telegram_message, mock_state)

            # Verify items were created
            from sqlalchemy import select
            stmt = select(ShoppingListItem).where(ShoppingListItem.user_id == sample_user.id)
            result = await db_session.execute(stmt)
            items = result.scalars().all()
            assert len(items) == 3
            assert {item.product_name for item in items} == {"Молоко", "Хлеб", "Яйца"}

            # Verify state was cleared
            mock_state.clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_bought(self, db_session, mock_callback_query, sample_user):
        """Test marking item as bought."""
        item = ShoppingListItem(
            user_id=sample_user.id,
            product_name="Тест",
            is_bought=False
        )
        db_session.add(item)
        await db_session.commit()

        mock_callback_query.data = f"shop_buy:{item.id}"

        with patch('handlers.shopping_list.get_db') as mock_get_db:
            async def db_generator():
                yield db_session
            mock_get_db.return_value = db_generator()

            with patch('handlers.shopping_list.show_shopping_list') as mock_show:
                await shopping_list.mark_bought(mock_callback_query)

                # Verify item was updated
                await db_session.refresh(item)
                assert item.is_bought is True

                # Verify list was refreshed
                mock_show.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_unbought(self, db_session, mock_callback_query, sample_user):
        """Test marking item as not bought."""
        item = ShoppingListItem(
            user_id=sample_user.id,
            product_name="Тест",
            is_bought=True
        )
        db_session.add(item)
        await db_session.commit()

        mock_callback_query.data = f"shop_unbuy:{item.id}"

        with patch('handlers.shopping_list.get_db') as mock_get_db:
            async def db_generator():
                yield db_session
            mock_get_db.return_value = db_generator()

            with patch('handlers.shopping_list.show_shopping_list') as mock_show:
                await shopping_list.mark_unbought(mock_callback_query)

                # Verify item was updated
                await db_session.refresh(item)
                assert item.is_bought is False

                # Verify list was refreshed
                mock_show.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_bought(self, db_session, mock_callback_query, sample_user):
        """Test clearing bought items."""
        item1 = ShoppingListItem(
            user_id=sample_user.id,
            product_name="Тест1",
            is_bought=True
        )
        item2 = ShoppingListItem(
            user_id=sample_user.id,
            product_name="Тест2",
            is_bought=False
        )
        db_session.add(item1)
        db_session.add(item2)
        await db_session.commit()

        with patch('handlers.shopping_list.get_db') as mock_get_db:
            async def db_generator():
                yield db_session
            mock_get_db.return_value = db_generator()

            with patch('handlers.shopping_list.show_shopping_list') as mock_show:
                await shopping_list.clear_bought(mock_callback_query)

                # Verify bought item was deleted
                from sqlalchemy import select
                stmt = select(ShoppingListItem).where(ShoppingListItem.user_id == sample_user.id)
                result = await db_session.execute(stmt)
                items = result.scalars().all()
                assert len(items) == 1
                assert items[0].product_name == "Тест2"

                # Verify list was refreshed
                mock_show.assert_called_once()


class TestUserSettingsHandler:
    """Tests for user settings handler."""

    @pytest.mark.asyncio
    async def test_show_settings_no_settings(
        self, db_session, mock_callback_query, sample_user
    ):
        """Test showing settings when user has no settings."""
        with patch('handlers.user_settings.get_db') as mock_get_db:
            async def db_generator():
                yield db_session
            mock_get_db.return_value = db_generator()

            await user_settings.show_settings(mock_callback_query)

            # Verify callback was answered
            mock_callback_query.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_show_settings_with_settings(
        self, db_session, mock_callback_query, sample_user
    ):
        """Test showing settings when user has settings."""
        settings = UserSettings(
            user_id=sample_user.id,
            daily_calories=2000.0,
            daily_protein=100.0,
            daily_fat=50.0,
            daily_carbs=200.0
        )
        db_session.add(settings)
        await db_session.commit()

        with patch('handlers.user_settings.get_db') as mock_get_db:
            async def db_generator():
                yield db_session
            mock_get_db.return_value = db_generator()

            await user_settings.show_settings(mock_callback_query)

            # Verify callback was answered
            mock_callback_query.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_edit_goals(self, mock_callback_query, mock_fsm_context):
        """Test starting edit goals flow."""
        await user_settings.start_edit_goals(mock_callback_query, mock_fsm_context)

        # Verify state was set
        mock_fsm_context.set_state.assert_called()
        # Verify callback was answered
        mock_callback_query.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_calories(self, db_session, mock_telegram_message, sample_user):
        """Test setting calories goal."""
        mock_telegram_message.text = "2000"

        mock_state = AsyncMock()
        mock_state.get_data = AsyncMock(return_value={"setting_type": "calories"})
        mock_state.update_data = AsyncMock()
        mock_state.set_state = AsyncMock()

        with patch('handlers.user_settings.get_db') as mock_get_db:
            async def db_generator():
                yield db_session
            mock_get_db.return_value = db_generator()

            await user_settings.set_calories(mock_telegram_message, mock_state)

            # Verify settings were created/updated
            from sqlalchemy import select
            stmt = select(UserSettings).where(UserSettings.user_id == sample_user.id)
            result = await db_session.execute(stmt)
            settings = result.scalar_one_or_none()
            assert settings is not None
            assert settings.daily_calories == 2000.0

    @pytest.mark.asyncio
    async def test_set_allergies(self, db_session, mock_telegram_message, sample_user):
        """Test setting allergies."""
        mock_telegram_message.text = "Орехи, Молоко"

        mock_state = AsyncMock()
        mock_state.clear = AsyncMock()

        with patch('handlers.user_settings.get_db') as mock_get_db:
            async def db_generator():
                yield db_session
            mock_get_db.return_value = db_generator()

            await user_settings.set_allergies(mock_telegram_message, mock_state)

            # Verify settings were created/updated
            from sqlalchemy import select
            stmt = select(UserSettings).where(UserSettings.user_id == sample_user.id)
            result = await db_session.execute(stmt)
            settings = result.scalar_one_or_none()
            assert settings is not None
            assert "Орехи" in settings.allergies
            assert "Молоко" in settings.allergies

