
import asyncio
from datetime import datetime, timedelta

from sqlalchemy import select

from database.base import get_db
from database.models import ConsumptionLog, UserSettings


async def simulate_tatiana():
    user_id = 5153798702
    last_week = datetime.now() - timedelta(days=7)

    # Референсные значения (на воду/базу)
    REF = {
        "коктейль": 100,
        "белок": 23,
        "оян": 18,
        "чай": 6,
        "алое": 2,
        "волокна": 15,
        "батончик": 200
    }

    async for session in get_db():
        settings_stmt = select(UserSettings).where(UserSettings.user_id == user_id)
        settings = (await session.execute(settings_stmt)).scalar_one_or_none()
        target_cal = settings.calorie_goal if settings else 1447

        stmt = select(ConsumptionLog).where(
            (ConsumptionLog.user_id == user_id) &
            (ConsumptionLog.date >= last_week)
        ).order_by(ConsumptionLog.date)

        logs = (await session.execute(stmt)).scalars().all()

        daily_official = {}
        daily_simulated = {}

        for l in logs:
            day = l.date.strftime("%Y-%m-%d")
            daily_official[day] = daily_official.get(day, 0) + l.calories

            # Расчет симуляции
            cal = l.calories
            if l.calories == 0:
                name = l.product_name.lower()
                for key, val in REF.items():
                    if key in name:
                        cal = val
                        break

            daily_simulated[day] = daily_simulated.get(day, 0) + cal

        print("--- Симуляция 'Честный дефицит' для Татьяны (последние 7 дней) ---")
        print(f"Цель: {target_cal} ккал\n")

        days = sorted(daily_official.keys())
        for d in days:
            off = daily_official[d]
            sim = daily_simulated[d]
            diff = sim - off
            status = "✅ Дефицит" if sim <= target_cal else "❌ ПЕРЕБОР"

            print(f"  {d}:")
            print(f"    - По боту: {off:4.0f} ккал")
            print(f"    - Реально: {sim:4.0f} ккал (+{diff:.0f} ккал)")
            print(f"    - Итог: {status}")

        avg_off = sum(daily_official.values()) / len(days)
        avg_sim = sum(daily_simulated.values()) / len(days)

        print("\nИТОГИ НЕДЕЛИ:")
        print(f"  Среднее по боту: {avg_off:.0f} ккал")
        print(f"  Среднее РЕАЛЬНОЕ: {avg_sim:.0f} ккал")
        print(f"  Разница (неучтенка): {avg_sim - avg_off:.0f} ккал в день")

if __name__ == "__main__":
    asyncio.run(simulate_tatiana())
