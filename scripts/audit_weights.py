
import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from sqlalchemy import select, func
from database.base import get_db
from database.models import Marathon, MarathonParticipant, User, WeightLog
from utils.user import get_user_display_name

async def main():
    async for session in get_db():
        # Get active marathon (Targeting ID 2 "Весна близко")
        stmt = select(Marathon).where(Marathon.id == 2)
        marathon = (await session.execute(stmt)).scalar_one_or_none()
        
        if not marathon:
            print("No active marathon found.")
            return

        print(f"🏆 Marathon: {marathon.name} (Start: {marathon.start_date.date()})")
        print("-" * 100)
        print(f"{'User':<20} | {'Stored Start':<12} | {'Calc Start':<12} | {'Current':<10} | {'Diff':<10} | {'Logs'}")
        print("-" * 100)

        # Get participants
        stmt = select(MarathonParticipant, User).join(User).where(MarathonParticipant.marathon_id == marathon.id)
        results = (await session.execute(stmt)).all()

        for part, user in results:
            # 1. Stored Start Weight
            stored_start = part.start_weight

            # 2. Calculated Start Weight (Logic from fix)
            # Find first log ON or AFTER start
            stmt_start = (
                select(WeightLog)
                .where(WeightLog.user_id == user.id, WeightLog.recorded_at >= marathon.start_date)
                .order_by(WeightLog.recorded_at.asc())
                .limit(1)
            )
            calc_start_log = (await session.execute(stmt_start)).scalar_one_or_none()
            
            # If not found, try before
            if not calc_start_log:
                 stmt_before = (
                    select(WeightLog)
                    .where(WeightLog.user_id == user.id, WeightLog.recorded_at < marathon.start_date)
                    .order_by(WeightLog.recorded_at.desc())
                    .limit(1)
                )
                 calc_start_log = (await session.execute(stmt_before)).scalar_one_or_none()

            calc_start_val = calc_start_log.weight if calc_start_log else 0.0
            calc_start_date = calc_start_log.recorded_at.date() if calc_start_log else "N/A"

            # 3. Current Weight
            stmt_curr = (
                select(WeightLog)
                .where(WeightLog.user_id == user.id)
                .order_by(WeightLog.recorded_at.desc())
                .limit(1)
            )
            curr_log = (await session.execute(stmt_curr)).scalar_one_or_none()
            curr_val = curr_log.weight if curr_log else 0.0
            curr_date = curr_log.recorded_at.date() if curr_log else "N/A"

            # Diff
            effective_start = stored_start if stored_start else calc_start_val
            diff = effective_start - curr_val if (effective_start and curr_val) else 0.0
            
            name = get_user_display_name(user)
            
            # Formatting
            stored_str = f"{stored_start:.1f}" if stored_start else "NULL ⚠️"
            calc_str = f"{calc_start_val:.1f} ({calc_start_date})"
            curr_str = f"{curr_val:.1f} ({curr_date})"
            
            print(f"{name:<20} | {stored_str:<12} | {calc_str:<12} | {curr_str:<10} | {diff:+.1f} kg")

if __name__ == "__main__":
    asyncio.run(main())
