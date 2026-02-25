#!/usr/bin/env python3
"""
FoodFlow Load Test — Safe & Isolated
=====================================
Tests internal functions WITHOUT Telegram API.
Results saved in real-time to prevent data loss on crash.

SAFETY:
- 60 second auto-timeout
- Uses test DB (not production)  
- AI calls go through Semaphore (max 5)
- Ctrl+C to stop immediately
"""
import asyncio
import sys
import os
import time
import random
import signal
from datetime import datetime
from dataclasses import dataclass, field
from typing import List

# Add project to path
sys.path.insert(0, '/home/user1/foodflow-bot')

# Results file — written in real-time
RESULTS_FILE = '/home/user1/foodflow-bot/load_test_results.log'
TIMEOUT_SECONDS = 60

@dataclass
class TestResult:
    action: str
    success: bool
    duration_ms: float
    error: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

# Global results storage
results: List[TestResult] = []
start_time: float = 0
stopped = False

def save_result(result: TestResult):
    """Save result immediately to file (crash-safe)."""
    with open(RESULTS_FILE, 'a') as f:
        status = "✅" if result.success else "❌"
        f.write(f"{result.timestamp} | {status} {result.action:25} | {result.duration_ms:7.1f}ms | {result.error}\n")
    results.append(result)

def print_progress():
    """Print live progress."""
    elapsed = time.time() - start_time
    success = sum(1 for r in results if r.success)
    failed = len(results) - success
    avg_ms = sum(r.duration_ms for r in results) / len(results) if results else 0
    print(f"\r⏱️ {elapsed:.0f}s | ✅ {success} | ❌ {failed} | avg {avg_ms:.0f}ms", end="", flush=True)

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully."""
    global stopped
    stopped = True
    print("\n\n🛑 STOPPED BY USER")
    print_summary()
    sys.exit(0)

def print_summary():
    """Print final summary."""
    if not results:
        print("No results collected.")
        return
    
    success = sum(1 for r in results if r.success)
    failed = len(results) - success
    total = len(results)
    
    durations = [r.duration_ms for r in results if r.success]
    avg_ms = sum(durations) / len(durations) if durations else 0
    p95 = sorted(durations)[int(len(durations) * 0.95)] if len(durations) > 10 else max(durations) if durations else 0
    
    print("\n" + "="*60)
    print("📊 LOAD TEST RESULTS")
    print("="*60)
    print(f"Total requests:  {total}")
    print(f"Success:         {success} ({100*success/total:.1f}%)")
    print(f"Failed:          {failed} ({100*failed/total:.1f}%)")
    print(f"Avg response:    {avg_ms:.0f}ms")
    print(f"P95 response:    {p95:.0f}ms")
    print(f"Duration:        {time.time() - start_time:.1f}s")
    print(f"\n📁 Full log: {RESULTS_FILE}")
    print("="*60)

# ============ TEST ACTIONS ============

async def test_ai_brain_analyze():
    """Test AI Brain text analysis."""
    from services.ai_brain import AIBrainService
    
    texts = [
        "съел яблоко",
        "купил молоко",
        "банан 200г",
        "на завтрак овсянку",
        "в холодильник сыр",
    ]
    
    text = random.choice(texts)
    start = time.time()
    try:
        result = await AIBrainService.analyze_text(text)
        duration = (time.time() - start) * 1000
        save_result(TestResult("AI_BRAIN_ANALYZE", True, duration))
    except Exception as e:
        duration = (time.time() - start) * 1000
        save_result(TestResult("AI_BRAIN_ANALYZE", False, duration, str(e)[:50]))

async def test_db_read():
    """Test database read (product list)."""
    from database.base import async_session
    from database.models import Product
    from sqlalchemy import select
    
    start = time.time()
    try:
        async with async_session() as session:
            stmt = select(Product).limit(10)
            await session.execute(stmt)
        duration = (time.time() - start) * 1000
        save_result(TestResult("DB_READ_PRODUCTS", True, duration))
    except Exception as e:
        duration = (time.time() - start) * 1000
        save_result(TestResult("DB_READ_PRODUCTS", False, duration, str(e)[:50]))

async def test_db_write():
    """Test database write (insert product)."""
    from database.base import async_session
    from database.models import Product
    
    start = time.time()
    try:
        async with async_session() as session:
            product = Product(
                user_id=999999999,  # Test user
                name=f"Test Product {random.randint(1000,9999)}",
                price=0.0,
                source="load_test"
            )
            session.add(product)
            await session.commit()
        duration = (time.time() - start) * 1000
        save_result(TestResult("DB_WRITE_PRODUCT", True, duration))
    except Exception as e:
        duration = (time.time() - start) * 1000
        save_result(TestResult("DB_WRITE_PRODUCT", False, duration, str(e)[:50]))

async def test_normalization():
    """Simple test action with delay."""
    start = time.time()
    try:
        await asyncio.sleep(random.uniform(0.05, 0.15))  # Simulate light work
        duration = (time.time() - start) * 1000
        save_result(TestResult("LIGHT_ACTION", True, duration))
    except Exception as e:
        duration = (time.time() - start) * 1000
        save_result(TestResult("LIGHT_ACTION", False, duration, str(e)[:50]))

# ============ MAIN TEST RUNNER ============

async def run_single_user(user_id: int):
    """Simulate one user doing random actions."""
    actions = [
        (test_ai_brain_analyze, 40),   # 40% weight
        (test_db_read, 30),             # 30%
        (test_db_write, 15),            # 15%
        (test_normalization, 15),       # 15%
    ]
    
    # Weighted random choice
    total = sum(w for _, w in actions)
    r = random.randint(1, total)
    cumulative = 0
    for action, weight in actions:
        cumulative += weight
        if r <= cumulative:
            await action()
            break
    
    # Small delay between actions
    await asyncio.sleep(random.uniform(0.1, 0.5))

async def run_load_test(concurrent_users: int = 20, duration_seconds: int = TIMEOUT_SECONDS):
    """Main load test with timeout."""
    global start_time, stopped
    
    # Clear results file
    with open(RESULTS_FILE, 'w') as f:
        f.write(f"=== LOAD TEST STARTED: {datetime.now().isoformat()} ===\n")
        f.write(f"Concurrent users: {concurrent_users}, Timeout: {duration_seconds}s\n")
        f.write("="*70 + "\n")
    
    print(f"🚀 Starting Load Test: {concurrent_users} concurrent users, {duration_seconds}s timeout")
    print(f"📁 Results: {RESULTS_FILE}")
    print("Press Ctrl+C to stop\n")
    
    start_time = time.time()
    end_time = start_time + duration_seconds
    
    async def user_loop(user_id):
        while time.time() < end_time and not stopped:
            await run_single_user(user_id)
            print_progress()
    
    # Create concurrent user tasks
    tasks = [asyncio.create_task(user_loop(i)) for i in range(concurrent_users)]
    
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        pass
    
    print_summary()

async def cleanup_test_data():
    """Remove test products after test."""
    from database.base import async_session
    from database.models import Product
    from sqlalchemy import delete
    
    async with async_session() as session:
        await session.execute(delete(Product).where(Product.user_id == 999999999))
        await session.commit()
    print("🧹 Cleaned up test data")

if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("="*60)
    print("🧪 FOODFLOW LOAD TEST")
    print("="*60)
    
    try:
        asyncio.run(run_load_test(concurrent_users=20, duration_seconds=60))
        asyncio.run(cleanup_test_data())
    except KeyboardInterrupt:
        print("\n🛑 Interrupted")
        print_summary()
