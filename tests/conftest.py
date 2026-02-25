"""
Pytest fixtures for FoodFlow Bot tests.
"""
import os
from unittest.mock import AsyncMock, MagicMock

import pytest
from aioresponses import aioresponses
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Set test environment variables before importing modules
os.environ['DATABASE_URL'] = "sqlite+aiosqlite:///:memory:"
os.environ['BOT_TOKEN'] = "test-token"
os.environ['OPENROUTER_API_KEY'] = "test-key"

# Import all models to ensure they are registered with Base.metadata
from database.base import Base
from database.models import (
    Product,
    Receipt,
    User,
    UserSettings,
)

# In-memory SQLite database for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="function")
async def db_session():
    """Create an in-memory SQLite database session for testing."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    # Create all tables - ensure all models are imported first
    # This creates: users, receipts, products, consumption_logs,
    # shopping_sessions, label_scans, price_tags, user_settings,
    # shopping_list_items, cached_recipes
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session
    async with async_session() as session:
        yield session
        await session.rollback()

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def mock_openrouter_response():
    """Mock successful OpenRouter API response."""
    return {
        "choices": [
            {
                "message": {
                    "content": '{"items": [{"name": "Молоко", "price": 100.0, "quantity": 1.0}], "total": 100.0}'
                }
            }
        ]
    }


@pytest.fixture
def mock_openrouter_error_response():
    """Mock OpenRouter API error response."""
    return {
        "error": {
            "message": "Rate limit exceeded",
            "type": "rate_limit_error"
        }
    }


@pytest.fixture
def mock_normalization_response():
    """Mock successful normalization API response."""
    return {
        "choices": [
            {
                "message": {
                    "content": '{"normalized": [{"original": "Молоко", "name": "Молоко 1л", "category": "Молочные продукты", "calories": 64}]}'
                }
            }
        ]
    }


@pytest.fixture
def aioresp():
    """Fixture for mocking aiohttp calls."""
    with aioresponses() as m:
        yield m


@pytest.fixture
def mock_telegram_user():
    """Mock Telegram User object."""
    user = MagicMock()
    user.id = 123456789
    user.username = "test_user"
    user.first_name = "Test"
    user.last_name = "User"
    return user


@pytest.fixture
def mock_telegram_message(mock_telegram_user):
    """Mock Telegram Message object."""
    message = MagicMock()
    message.from_user = mock_telegram_user
    message.message_id = 1
    message.text = None
    message.photo = None
    message.answer = AsyncMock()
    message.reply = AsyncMock()
    message.edit_text = AsyncMock()
    message.edit_media = AsyncMock()
    message.delete = AsyncMock()
    return message


@pytest.fixture
def mock_callback_query(mock_telegram_user, mock_telegram_message):
    """Mock Telegram CallbackQuery object."""
    callback = MagicMock()
    callback.from_user = mock_telegram_user
    callback.message = mock_telegram_message
    callback.data = "test_callback"
    callback.answer = AsyncMock()
    return callback


@pytest.fixture
def mock_bot():
    """Mock Telegram Bot object."""
    bot = MagicMock()
    bot.get_file = AsyncMock()
    bot.download_file = AsyncMock()
    return bot


@pytest.fixture
def mock_fsm_context():
    """Mock FSM Context for state management."""
    context = MagicMock()
    context.get_state = AsyncMock(return_value=None)
    context.set_state = AsyncMock()
    context.update_data = AsyncMock()
    context.get_data = AsyncMock(return_value={})
    context.clear = AsyncMock()
    return context


@pytest.fixture
def sample_user_data():
    """Sample user data for testing."""
    return {
        "id": 123456789,
        "username": "test_user"
    }


@pytest.fixture
def sample_receipt_data(sample_user_data):
    """Sample receipt data for testing."""
    return {
        "user_id": sample_user_data["id"],
        "total_amount": 500.0,
        "raw_text": "Test receipt"
    }


@pytest.fixture
def sample_product_data():
    """Sample product data for testing."""
    return {
        "name": "Молоко",
        "price": 100.0,
        "quantity": 1.0,
        "category": "Молочные продукты",
        "calories": 64.0
    }


@pytest.fixture
async def sample_user(db_session, sample_user_data):
    """Create a sample user in the database."""
    user = User(id=sample_user_data["id"], username=sample_user_data["username"])
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def sample_receipt(db_session, sample_user, sample_receipt_data):
    """Create a sample receipt in the database."""
    receipt = Receipt(
        user_id=sample_receipt_data["user_id"],
        total_amount=sample_receipt_data["total_amount"],
        raw_text=sample_receipt_data["raw_text"]
    )
    db_session.add(receipt)
    await db_session.commit()
    await db_session.refresh(receipt)
    return receipt


@pytest.fixture
async def sample_product(db_session, sample_receipt, sample_product_data):
    """Create a sample product in the database."""
    product = Product(
        receipt_id=sample_receipt.id,
        name=sample_product_data["name"],
        price=sample_product_data["price"],
        quantity=sample_product_data["quantity"],
        category=sample_product_data["category"],
        calories=sample_product_data["calories"]
    )
    db_session.add(product)
    await db_session.commit()
    await db_session.refresh(product)
    return product


@pytest.fixture
async def sample_user_settings(db_session, sample_user):
    """Create a sample user settings with full profile."""
    settings = UserSettings(
        user_id=sample_user.id,
        gender="male",
        height=180,
        weight=80.0,
        goal="lose_weight",
        calorie_goal=2000,
        protein_goal=150,
        fat_goal=70,
        carb_goal=250,
        is_initialized=True,
    )
    db_session.add(settings)
    await db_session.commit()
    await db_session.refresh(settings)
    return settings

