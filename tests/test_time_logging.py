import asyncio
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select

from database.base import get_db
from database.models import ConsumptionLog


@pytest.mark.asyncio
async def test_single_save_with_time(db_session):
    print("🧪 Testing single log save with custom time...")
    test_user_id = 999999
    custom_time = datetime.now() - timedelta(hours=2)

    with patch('database.base.get_db') as mock_get_db:
        async def db_generator():
            yield db_session
        mock_get_db.return_value = db_generator()

        log = ConsumptionLog(
            user_id=test_user_id,
            product_name="Test Product",
            calories=100,
            protein=10,
            fat=5,
            carbs=20,
            fiber=2,
            date=custom_time
        )
        db_session.add(log)
        await db_session.commit()

        # Verify
        stmt = select(ConsumptionLog).where(ConsumptionLog.user_id == test_user_id).order_by(ConsumptionLog.id.desc()).limit(1)
        result = await db_session.execute(stmt)
        saved_log = result.scalar_one_or_none()

        assert saved_log is not None
        assert saved_log.product_name == "Test Product"
        # Database might strip microseconds, so compare with tolerance
        assert abs((saved_log.date - custom_time).total_seconds()) < 1.0
        print(f"✅ Single log saved correctly with time: {saved_log.date}")

@pytest.mark.asyncio
async def test_batch_save_with_time(db_session):
    print("🧪 Testing batch log save with custom time...")
    test_user_id = 999999
    custom_time = datetime.now().replace(hour=13, minute=0, second=0, microsecond=0)

    items = [
        {"name": "Batch Item 1", "calories": 50, "protein": 5, "fat": 2, "carbs": 10, "fiber": 1},
        {"name": "Batch Item 2", "calories": 150, "protein": 15, "fat": 7, "carbs": 30, "fiber": 3}
    ]

    with patch('database.base.get_db') as mock_get_db:
        async def db_generator():
            yield db_session
        mock_get_db.return_value = db_generator()

        for item in items:
            log = ConsumptionLog(
                user_id=test_user_id,
                product_name=item["name"],
                calories=item["calories"],
                protein=item["protein"],
                fat=item["fat"],
                carbs=item["carbs"],
                fiber=item["fiber"],
                date=custom_time
            )
            db_session.add(log)
        await db_session.commit()

        # Verify
        stmt = select(ConsumptionLog).where(ConsumptionLog.user_id == test_user_id, ConsumptionLog.product_name.like("Batch Item%"))
        result = await db_session.execute(stmt)
        saved_logs = result.scalars().all()

        assert len(saved_logs) == 2
        for log in saved_logs:
             assert abs((log.date - custom_time).total_seconds()) < 1.0
        print(f"✅ Batch logs saved correctly with time: {custom_time}")
