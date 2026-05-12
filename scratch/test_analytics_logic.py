import asyncio
import json
import time

from sqlalchemy import delete, select

from database.base import get_db
from database.models import ProductEvent
from handlers.onboarding import handle_onboarding_cancel
from utils.analytics import log_event

TEST_USER_ID = 123456

class MockMessage:
    def __init__(self, chat_id):
        self.chat = type('obj', (object,), {'id': chat_id, 'first_name': 'Test'})
        self.from_user = self.chat
    async def edit_text(self, text, **kwargs):
        print(f"      [Bot Response]: {text[:50]}...")
        return True
    async def answer(self, text, **kwargs):
        print(f"      [Bot Response]: {text[:50]}...")
        return True

class MockCallback:
    def __init__(self, user_id):
        self.from_user = type('obj', (object,), {'id': user_id, 'first_name': 'Test'})
        self.message = MockMessage(user_id)
        self.data = "onboarding_cancel"
    async def answer(self, text=None, **kwargs):
        return True

class MockState:
    def __init__(self):
        self.data = {}
        self.state = "OnboardingStates:waiting_for_weight"
    async def get_data(self): return self.data
    async def update_data(self, **kwargs): self.data.update(kwargs)
    async def get_state(self): return self.state
    async def set_state(self, state): self.state = state
    async def clear(self): self.data = {}; self.state = None

async def test_pain_signals():
    print(f"--- Starting Advanced Pain Signals Test (User {TEST_USER_ID}) ---")

    async for session in get_db():
        # 1. Cleanup
        await session.execute(delete(ProductEvent).where(ProductEvent.user_id == TEST_USER_ID))
        await session.commit()

        # 2. Test Onboarding Abandonment
        print("\n[Test 1] Simulating Onboarding Abandonment...")
        state = MockState()
        callback = MockCallback(TEST_USER_ID)
        await handle_onboarding_cancel(callback, state)

        # 3. Test Rage Back (Logic simulation)
        print("\n[Test 2] Simulating Rage Back (Fast clicks)...")
        # Click 1
        await state.update_data(last_back_time=time.time())
        # Click 2 (0.5s later)
        time.sleep(0.5)
        last_back = (await state.get_data()).get("last_back_time", 0)
        if time.time() - last_back < 2.0:
            await log_event(TEST_USER_ID, "rage_back", {"step": "test_mock"})
            print("      Rage back detected and logged.")

        # 4. Test Vision Pain Threshold
        print("\n[Test 3] Simulating Vision Latency > 5s...")
        fake_latency = 6500
        await log_event(TEST_USER_ID, "vision_latency", {"ms": fake_latency, "success": True})
        if fake_latency > 5000:
            await log_event(TEST_USER_ID, "vision_pain_threshold_hit", {"ms": fake_latency})
            print("      Vision pain threshold hit logged.")

        # 5. Verify DB
        stmt = select(ProductEvent).where(ProductEvent.user_id == TEST_USER_ID).order_by(ProductEvent.created_at.asc())
        result = await session.execute(stmt)
        events = result.scalars().all()

        print(f"\nSummary: Found {len(events)} events in DB:")
        for ev in events:
            print(f"  - {ev.event_name}: {json.dumps(ev.payload, ensure_ascii=False)}")

        expected = ["onboarding_abandoned", "rage_back", "vision_pain_threshold_hit"]
        found_names = [e.event_name for e in events]

        for name in expected:
            if name in found_names:
                print(f"✅ Event '{name}' verified.")
            else:
                print(f"❌ Event '{name}' NOT FOUND.")

        break

if __name__ == "__main__":
    asyncio.run(test_pain_signals())
