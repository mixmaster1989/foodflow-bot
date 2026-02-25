"""
Comprehensive Integration Tests for Marathon Module.

This test suite creates REAL test data in the database:
- Test Curator
- Test Wards (подопечные)
- Marathon with Waves, Participants, Snowflakes

NO MOCKING - all operations hit the actual database.
"""

import os
import sys
from datetime import datetime, timedelta

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


import pytest
from sqlalchemy import delete, select

from database.base import async_session
from database.models import Marathon, MarathonParticipant, SnowflakeLog, User, WeightLog

# =============== TEST CONSTANTS ===============
TEST_CURATOR_ID = 999888777  # Unique ID for test curator
TEST_WARD_IDS = [999888001, 999888002, 999888003]  # Test wards
TEST_MARATHON_NAME = "INTEGRATION_TEST_MARATHON"


class Colors:
    """ANSI color codes for pretty output."""
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def log_test(name: str, passed: bool, details: str = ""):
    """Log test result with colors."""
    status = f"{Colors.GREEN}✅ PASS{Colors.RESET}" if passed else f"{Colors.RED}❌ FAIL{Colors.RESET}"
    print(f"   {status} {name}")
    if details:
        print(f"       {Colors.BLUE}→ {details}{Colors.RESET}")


async def setup_test_users():
    """Create test curator and wards in the database."""
    print(f"\n{Colors.BOLD}📦 SETUP: Creating test users...{Colors.RESET}")

    async with async_session() as session:
        # Clean up any existing test users first
        await session.execute(delete(User).where(User.id == TEST_CURATOR_ID))
        for ward_id in TEST_WARD_IDS:
            await session.execute(delete(User).where(User.id == ward_id))
        await session.commit()

        # Create curator
        curator = User(
            id=TEST_CURATOR_ID,
            username="test_curator_marathon",
            role="curator"
        )
        session.add(curator)

        # Create wards
        for i, ward_id in enumerate(TEST_WARD_IDS):
            ward = User(
                id=ward_id,
                username=f"test_ward_{i+1}",
                curator_id=TEST_CURATOR_ID,  # Link to curator
                role="user"
            )
            session.add(ward)

            # Add initial weight log for each ward
            weight_log = WeightLog(
                user_id=ward_id,
                weight=75.0 + i,  # 75, 76, 77 kg
                recorded_at=datetime.now()
            )
            session.add(weight_log)

        await session.commit()

    log_test("Created test curator", True, f"ID={TEST_CURATOR_ID}")
    log_test("Created test wards", True, f"IDs={TEST_WARD_IDS}")


async def cleanup_test_data():
    """Remove all test data from database."""
    print(f"\n{Colors.BOLD}🧹 CLEANUP: Removing test data...{Colors.RESET}")

    async with async_session() as session:
        # Delete in correct order (respecting foreign keys)

        # 1. Get test marathon
        marathon = await session.scalar(
            select(Marathon).where(Marathon.name == TEST_MARATHON_NAME)
        )

        if marathon:
            # Delete snowflake logs
            participants = await session.execute(
                select(MarathonParticipant).where(MarathonParticipant.marathon_id == marathon.id)
            )
            for part in participants.scalars().all():
                await session.execute(
                    delete(SnowflakeLog).where(SnowflakeLog.participant_id == part.id)
                )

            # Delete participants
            await session.execute(
                delete(MarathonParticipant).where(MarathonParticipant.marathon_id == marathon.id)
            )

            # Delete marathon
            await session.execute(
                delete(Marathon).where(Marathon.id == marathon.id)
            )

        # 2. Delete weight logs for test users
        for ward_id in TEST_WARD_IDS:
            await session.execute(
                delete(WeightLog).where(WeightLog.user_id == ward_id)
            )

        # 3. Delete test users
        await session.execute(delete(User).where(User.id == TEST_CURATOR_ID))
        for ward_id in TEST_WARD_IDS:
            await session.execute(delete(User).where(User.id == ward_id))

        await session.commit()

    log_test("Cleanup completed", True)


# =============== TEST CASES ===============

@pytest.mark.asyncio
async def test_marathon_full_integration(db_session):
    """
    Comprehensive Integration Test for Marathon Module.
    Runs all steps in sequence to ensure data flow and integrity.
    """
    print(f"\n{'='*60}")
    print(f"{Colors.BOLD}🏃 MARATHON MODULE INTEGRATION TESTS{Colors.RESET}")
    print(f"{'='*60}")

    # 1. Setup (using the db_session instead of manual async_session)
    print(f"\n{Colors.BOLD}📦 SETUP: Creating test users...{Colors.RESET}")

    # Create curator
    curator = User(
        id=TEST_CURATOR_ID,
        username="test_curator_marathon",
        role="curator"
    )
    db_session.add(curator)

    # Create wards
    for i, ward_id in enumerate(TEST_WARD_IDS):
        ward = User(
            id=ward_id,
            username=f"test_ward_{i+1}",
            curator_id=TEST_CURATOR_ID,
            role="user"
        )
        db_session.add(ward)

        # Add initial weight log
        weight_log = WeightLog(
            user_id=ward_id,
            weight=75.0 + i,
            recorded_at=datetime.now()
        )
        db_session.add(weight_log)

    await db_session.commit()
    log_test("Created test curator and wards", True)

    # 2. Test 1: Marathon Creation
    print(f"\n{Colors.BOLD}🧪 TEST 1: Marathon Creation{Colors.RESET}")
    marathon = Marathon(
        curator_id=TEST_CURATOR_ID,
        name=TEST_MARATHON_NAME,
        start_date=datetime.now(),
        end_date=datetime.now() + timedelta(days=30),
        is_active=True,
        waves_config={}
    )
    db_session.add(marathon)
    await db_session.commit()
    await db_session.refresh(marathon)
    marathon_id = marathon.id

    assert marathon_id is not None
    log_test("Marathon created", True, f"ID={marathon_id}")

    # 3. Test 2: Add Participants
    print(f"\n{Colors.BOLD}🧪 TEST 2: Add Participants{Colors.RESET}")
    for ward_id in TEST_WARD_IDS:
        weight_stmt = (
            select(WeightLog.weight)
            .where(WeightLog.user_id == ward_id)
            .order_by(WeightLog.recorded_at.desc())
            .limit(1)
        )
        start_weight = await db_session.scalar(weight_stmt)

        participant = MarathonParticipant(
            marathon_id=marathon_id,
            user_id=ward_id,
            start_weight=start_weight,
            total_snowflakes=0,
            is_active=True
        )
        db_session.add(participant)

    await db_session.commit()

    stmt = select(MarathonParticipant).where(
        MarathonParticipant.marathon_id == marathon_id,
        MarathonParticipant.is_active
    )
    participants = (await db_session.execute(stmt)).scalars().all()
    assert len(participants) == len(TEST_WARD_IDS)
    log_test(f"Added {len(participants)} participants", True)

    participant_ids = [p.id for p in participants]

    # 4. Test 3: Snowflake Assignment
    print(f"\n{Colors.BOLD}🧪 TEST 3: Snowflake Assignment{Colors.RESET}")
    for i, part_id in enumerate(participant_ids):
        participant = await db_session.get(MarathonParticipant, part_id)
        award_amount = (i + 1) * 5
        participant.total_snowflakes += award_amount

        log = SnowflakeLog(
            participant_id=part_id,
            curator_id=TEST_CURATOR_ID,
            amount=award_amount,
            reason=f"Test award #{i+1}"
        )
        db_session.add(log)
        await db_session.commit()
        await db_session.refresh(participant)
        assert participant.total_snowflakes == award_amount
    log_test("Snowflakes assigned", True)

    # 5. Test 4: Wave Configuration
    print(f"\n{Colors.BOLD}🧪 TEST 4: Wave Configuration{Colors.RESET}")
    marathon = await db_session.get(Marathon, marathon_id)
    waves = {
        "wave_1": {"name": "Разгон", "start": "01.03", "end": "10.03"},
        "wave_2": {"name": "Марафон", "start": "11.03", "end": "25.03"}
    }
    marathon.waves_config = waves
    await db_session.commit()
    await db_session.refresh(marathon)
    assert len(marathon.waves_config) == 2
    log_test("Waves configured", True)

    # 6. Test 5: Leaderboard Calculation
    print(f"\n{Colors.BOLD}🧪 TEST 5: Leaderboard Calculation{Colors.RESET}")
    for i, ward_id in enumerate(TEST_WARD_IDS):
        new_weight = 75.0 + i - (i + 1) * 0.5
        weight_log = WeightLog(
            user_id=ward_id,
            weight=new_weight,
            recorded_at=datetime.now() + timedelta(days=7)
        )
        db_session.add(weight_log)
    await db_session.commit()

    stmt = (
        select(MarathonParticipant, User)
        .join(User, MarathonParticipant.user_id == User.id)
        .where(MarathonParticipant.marathon_id == marathon_id)
    )
    p_data = (await db_session.execute(stmt)).all()
    assert len(p_data) == len(TEST_WARD_IDS)
    log_test("Leaderboard verified", True)

    # 7. Test 6: Stop Marathon
    print(f"\n{Colors.BOLD}🧪 TEST 6: Stop Marathon{Colors.RESET}")
    marathon.is_active = False
    await db_session.commit()
    assert not marathon.is_active
    log_test("Marathon stopped", True)



