"""
Comprehensive Integration Tests for Marathon Module.

This test suite creates REAL test data in the database:
- Test Curator
- Test Wards (подопечные)
- Marathon with Waves, Participants, Snowflakes

NO MOCKING - all operations hit the actual database.
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, delete
from database.base import async_session, init_db
from database.models import (
    User, Marathon, MarathonParticipant, SnowflakeLog, WeightLog
)

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
                recorded_at=datetime.utcnow()
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

async def test_1_marathon_creation():
    """Test: Curator creates a marathon."""
    print(f"\n{Colors.BOLD}🧪 TEST 1: Marathon Creation{Colors.RESET}")
    
    async with async_session() as session:
        # Verify curator exists
        curator = await session.get(User, TEST_CURATOR_ID)
        assert curator is not None, "Curator should exist"
        assert curator.role == "curator", "User should have curator role"
        log_test("Curator exists and has correct role", True)
        
        # Create marathon
        marathon = Marathon(
            curator_id=TEST_CURATOR_ID,
            name=TEST_MARATHON_NAME,
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=30),
            is_active=True,
            waves_config={}
        )
        session.add(marathon)
        await session.commit()
        await session.refresh(marathon)
        
        assert marathon.id is not None, "Marathon should have ID"
        assert marathon.is_active == True, "Marathon should be active"
        log_test("Marathon created", True, f"ID={marathon.id}")
        
        return marathon.id


async def test_2_add_participants(marathon_id: int):
    """Test: Add wards as marathon participants."""
    print(f"\n{Colors.BOLD}🧪 TEST 2: Add Participants{Colors.RESET}")
    
    async with async_session() as session:
        added_count = 0
        
        for ward_id in TEST_WARD_IDS:
            # Get latest weight for start_weight
            weight_stmt = (
                select(WeightLog.weight)
                .where(WeightLog.user_id == ward_id)
                .order_by(WeightLog.recorded_at.desc())
                .limit(1)
            )
            start_weight = await session.scalar(weight_stmt)
            
            participant = MarathonParticipant(
                marathon_id=marathon_id,
                user_id=ward_id,
                start_weight=start_weight,
                total_snowflakes=0,
                is_active=True
            )
            session.add(participant)
            added_count += 1
        
        await session.commit()
        
        # Verify
        stmt = select(MarathonParticipant).where(
            MarathonParticipant.marathon_id == marathon_id,
            MarathonParticipant.is_active == True
        )
        result = await session.execute(stmt)
        participants = result.scalars().all()
        
        assert len(participants) == len(TEST_WARD_IDS), f"Should have {len(TEST_WARD_IDS)} participants"
        log_test(f"Added {added_count} participants", True)
        
        # Verify start weights were captured
        for p in participants:
            assert p.start_weight is not None, "Start weight should be set"
            log_test(f"Ward {p.user_id} start_weight", True, f"{p.start_weight} kg")
        
        return [p.id for p in participants]


async def test_3_snowflake_assignment(participant_ids: list):
    """Test: Curator assigns snowflakes to participants."""
    print(f"\n{Colors.BOLD}🧪 TEST 3: Snowflake Assignment{Colors.RESET}")
    
    async with async_session() as session:
        for i, part_id in enumerate(participant_ids):
            participant = await session.get(MarathonParticipant, part_id)
            assert participant is not None, f"Participant {part_id} should exist"
            
            # Award snowflakes
            award_amount = (i + 1) * 5  # 5, 10, 15
            participant.total_snowflakes += award_amount
            
            # Log the award
            log = SnowflakeLog(
                participant_id=part_id,
                curator_id=TEST_CURATOR_ID,
                amount=award_amount,
                reason=f"Test award #{i+1}"
            )
            session.add(log)
            
            await session.commit()
            await session.refresh(participant)
            
            assert participant.total_snowflakes == award_amount, "Snowflakes should be updated"
            log_test(f"Participant {part_id}", True, f"+{award_amount} ❄️ = {participant.total_snowflakes}")
        
        # Verify logs were created
        for part_id in participant_ids:
            log_stmt = select(SnowflakeLog).where(SnowflakeLog.participant_id == part_id)
            logs = (await session.execute(log_stmt)).scalars().all()
            assert len(logs) > 0, "Snowflake log should exist"
        
        log_test("Snowflake logs created", True)


async def test_4_wave_configuration(marathon_id: int):
    """Test: Configure waves for marathon."""
    print(f"\n{Colors.BOLD}🧪 TEST 4: Wave Configuration{Colors.RESET}")
    
    async with async_session() as session:
        marathon = await session.get(Marathon, marathon_id)
        assert marathon is not None, "Marathon should exist"
        
        # Add waves
        waves = {
            "wave_1": {
                "name": "Разгон",
                "start": "01.03",
                "end": "10.03"
            },
            "wave_2": {
                "name": "Марафон",
                "start": "11.03",
                "end": "25.03"
            },
            "wave_3": {
                "name": "Финиш",
                "start": "26.03",
                "end": "30.03"
            }
        }
        
        marathon.waves_config = waves
        await session.commit()
        await session.refresh(marathon)
        
        # Verify
        assert marathon.waves_config is not None, "Waves config should be set"
        assert len(marathon.waves_config) == 3, "Should have 3 waves"
        log_test("Created 3 waves", True)
        
        for wave_id, wave_data in marathon.waves_config.items():
            log_test(f"Wave: {wave_data['name']}", True, f"{wave_data['start']} — {wave_data['end']}")
        
        # Test wave deletion
        # Important: SQLAlchemy doesn't track in-place dict mutations!
        # We need to either reassign or use flag_modified
        from sqlalchemy.orm.attributes import flag_modified
        
        waves_copy = dict(marathon.waves_config)
        del waves_copy["wave_3"]
        marathon.waves_config = waves_copy
        flag_modified(marathon, "waves_config")
        
        await session.commit()
        await session.refresh(marathon)
        
        assert len(marathon.waves_config) == 2, "Should have 2 waves after deletion"
        log_test("Deleted wave_3", True, "2 waves remaining")


async def test_5_leaderboard_calculation(marathon_id: int):
    """Test: Calculate leaderboard with weight loss."""
    print(f"\n{Colors.BOLD}🧪 TEST 5: Leaderboard Calculation{Colors.RESET}")
    
    async with async_session() as session:
        # Simulate weight loss by adding new weight logs
        for i, ward_id in enumerate(TEST_WARD_IDS):
            new_weight = 75.0 + i - (i + 1) * 0.5  # Lose 0.5, 1.0, 1.5 kg
            weight_log = WeightLog(
                user_id=ward_id,
                weight=new_weight,
                recorded_at=datetime.utcnow() + timedelta(days=7)  # "1 week later"
            )
            session.add(weight_log)
        await session.commit()
        
        # Calculate leaderboard
        stmt = (
            select(MarathonParticipant, User)
            .join(User, MarathonParticipant.user_id == User.id)
            .where(MarathonParticipant.marathon_id == marathon_id, MarathonParticipant.is_active == True)
        )
        result = await session.execute(stmt)
        participants = result.all()
        
        leaderboard = []
        for part, user in participants:
            # Get latest weight
            latest_stmt = (
                select(WeightLog.weight)
                .where(WeightLog.user_id == user.id)
                .order_by(WeightLog.recorded_at.desc())
                .limit(1)
            )
            current_weight = await session.scalar(latest_stmt)
            
            start_w = part.start_weight or 75.0
            current_w = current_weight or start_w
            
            loss_kg = start_w - current_w
            loss_pct = (loss_kg / start_w) * 100 if start_w > 0 else 0
            
            leaderboard.append({
                "name": user.username,
                "start": start_w,
                "current": current_w,
                "loss_kg": loss_kg,
                "loss_pct": loss_pct,
                "snowflakes": part.total_snowflakes
            })
        
        # Sort by % loss
        leaderboard.sort(key=lambda x: x["loss_pct"], reverse=True)
        
        assert len(leaderboard) == len(TEST_WARD_IDS), "Leaderboard should have all participants"
        log_test("Leaderboard calculated", True, f"{len(leaderboard)} entries")
        
        for i, entry in enumerate(leaderboard, 1):
            log_test(
                f"#{i} {entry['name']}", 
                True, 
                f"{entry['start']:.1f} → {entry['current']:.1f} kg (-{entry['loss_kg']:.1f} kg, {entry['loss_pct']:.1f}%) | ❄️{entry['snowflakes']}"
            )


async def test_6_stop_marathon(marathon_id: int):
    """Test: Stop marathon."""
    print(f"\n{Colors.BOLD}🧪 TEST 6: Stop Marathon{Colors.RESET}")
    
    async with async_session() as session:
        marathon = await session.get(Marathon, marathon_id)
        assert marathon is not None, "Marathon should exist"
        assert marathon.is_active == True, "Marathon should be active before stopping"
        
        marathon.is_active = False
        await session.commit()
        await session.refresh(marathon)
        
        assert marathon.is_active == False, "Marathon should be inactive"
        log_test("Marathon stopped", True, "is_active=False")


async def test_7_data_integrity():
    """Test: Verify all data relationships are correct."""
    print(f"\n{Colors.BOLD}🧪 TEST 7: Data Integrity Check{Colors.RESET}")
    
    async with async_session() as session:
        # Check curator has wards
        wards_stmt = select(User).where(User.curator_id == TEST_CURATOR_ID)
        wards = (await session.execute(wards_stmt)).scalars().all()
        assert len(wards) == len(TEST_WARD_IDS), "Curator should have correct number of wards"
        log_test("Curator-Ward relationship", True, f"{len(wards)} wards linked")
        
        # Check marathon exists
        marathon = await session.scalar(
            select(Marathon).where(Marathon.name == TEST_MARATHON_NAME)
        )
        assert marathon is not None, "Marathon should exist"
        log_test("Marathon exists", True)
        
        # Check participants linked to marathon
        parts_stmt = select(MarathonParticipant).where(
            MarathonParticipant.marathon_id == marathon.id
        )
        parts = (await session.execute(parts_stmt)).scalars().all()
        assert len(parts) == len(TEST_WARD_IDS), "All wards should be participants"
        log_test("Marathon-Participant relationship", True)
        
        # Check snowflake logs linked to participants
        for part in parts:
            logs_stmt = select(SnowflakeLog).where(SnowflakeLog.participant_id == part.id)
            logs = (await session.execute(logs_stmt)).scalars().all()
            assert len(logs) > 0, f"Participant {part.id} should have snowflake logs"
        log_test("Participant-SnowflakeLog relationship", True)


# =============== MAIN RUNNER ===============

async def run_all_tests():
    """Run all integration tests."""
    print(f"\n{'='*60}")
    print(f"{Colors.BOLD}🏃 MARATHON MODULE INTEGRATION TESTS{Colors.RESET}")
    print(f"{'='*60}")
    print(f"Database: REAL (no mocks)")
    print(f"Test Curator ID: {TEST_CURATOR_ID}")
    print(f"Test Ward IDs: {TEST_WARD_IDS}")
    print(f"{'='*60}")
    
    await init_db()
    
    passed = 0
    failed = 0
    marathon_id = None
    participant_ids = []
    
    try:
        # Setup
        await setup_test_users()
        
        # Run tests
        marathon_id = await test_1_marathon_creation()
        if marathon_id:
            passed += 1
            
            participant_ids = await test_2_add_participants(marathon_id)
            if participant_ids:
                passed += 1
                
                await test_3_snowflake_assignment(participant_ids)
                passed += 1
                
                await test_4_wave_configuration(marathon_id)
                passed += 1
                
                await test_5_leaderboard_calculation(marathon_id)
                passed += 1
                
                await test_6_stop_marathon(marathon_id)
                passed += 1
                
                await test_7_data_integrity()
                passed += 1
        
    except AssertionError as e:
        print(f"\n{Colors.RED}❌ ASSERTION FAILED: {e}{Colors.RESET}")
        failed += 1
    except Exception as e:
        print(f"\n{Colors.RED}❌ ERROR: {e}{Colors.RESET}")
        import traceback
        traceback.print_exc()
        failed += 1
    finally:
        # Always cleanup
        await cleanup_test_data()
    
    # Summary
    print(f"\n{'='*60}")
    if failed == 0:
        print(f"{Colors.GREEN}{Colors.BOLD}✅ ALL {passed} TESTS PASSED!{Colors.RESET}")
    else:
        print(f"{Colors.RED}{Colors.BOLD}❌ {failed} TESTS FAILED, {passed} PASSED{Colors.RESET}")
    print(f"{'='*60}\n")
    
    return 1 if failed > 0 else 0


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
