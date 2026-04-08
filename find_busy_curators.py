
import asyncio
from sqlalchemy import text, select, func
from database.base import get_db
from database.models import User, ConsumptionLog
from datetime import date

async def find_busy_curators():
    yesterday = date(2026, 3, 26)
    async for session in get_db():
        # Curators with most wards
        group_stmt = select(User.curator_id, func.count()).where(User.curator_id.isnot(None)).group_by(User.curator_id).order_by(func.count().desc()).limit(10)
        curators = (await session.execute(group_stmt)).all()
        for cid, count in curators:
            # Active wards yesterday
            active_stmt = select(func.count(func.distinct(ConsumptionLog.user_id))).join(User, User.id == ConsumptionLog.user_id).where(User.curator_id == cid, func.date(ConsumptionLog.date) == yesterday)
            active_count = (await session.execute(active_stmt)).scalar()
            print(f"Curator {cid}: {count} wards, {active_count} active yesterday")
        break

if __name__ == "__main__":
    asyncio.run(find_busy_curators())
