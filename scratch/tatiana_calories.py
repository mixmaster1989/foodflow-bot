
import asyncio
from datetime import datetime, timedelta

from sqlalchemy import func, select

from database.base import get_db
from database.models import ConsumptionLog, UserSettings


async def calculate_tatiana_calories():
    user_id = 5153798702
    last_week = datetime.now() - timedelta(days=7)

    async for session in get_db():
        # 1. Получаем целевые показатели
        settings_stmt = select(UserSettings).where(UserSettings.user_id == user_id)
        settings = (await session.execute(settings_stmt)).scalar_one_or_none()
        target_cal = settings.calorie_goal if settings else 1447

        # 2. Получаем логи за неделю
        stmt = select(
            func.date(ConsumptionLog.date).label('day'),
            func.sum(ConsumptionLog.calories).label('total_cal'),
            func.sum(ConsumptionLog.protein).label('total_p'),
            func.sum(ConsumptionLog.fat).label('total_f'),
            func.sum(ConsumptionLog.carbs).label('total_c')
        ).where(
            (ConsumptionLog.user_id == user_id) &
            (ConsumptionLog.date >= last_week)
        ).group_by('day')

        results = (await session.execute(stmt)).all()

        print("--- Анализ питания Татьяны Безручкиной (последние 7 дней) ---")
        print(f"Цель: {target_cal} ккал\n")

        if not results:
            print("Нет данных о питании за этот период.")
            return

        total_days = len(results)
        sum_cal = 0
        sum_p = 0
        sum_f = 0
        sum_c = 0

        for row in results:
            day, cal, p, f, c = row
            sum_cal += cal
            sum_p += p
            sum_f += f
            sum_c += c
            status = "✅ Ок" if cal <= target_cal + 100 else "⚠️ Перебор"
            print(f"  {day}: {cal:.0f} ккал | Б:{p:.0f} Ж:{f:.0f} У:{c:.0f} | {status}")

        avg_cal = sum_cal / total_days
        avg_p = sum_p / total_days
        avg_f = sum_f / total_days
        avg_c = sum_c / total_days

        print("\nСРЕДНИЕ ПОКАЗАТЕЛИ ЗА НЕДЕЛЮ:")
        print(f"  🔥 Калории: {avg_cal:.0f} ккал (Цель: {target_cal})")
        print(f"  🥩 Белки: {avg_p:.1f} г")
        print(f"  🥑 Жиры: {avg_f:.1f} г")
        print(f"  🍞 Углеводы: {avg_c:.1f} г")

        deviation = avg_cal - target_cal
        if deviation > 0:
            print(f"\nВывод: В среднем Татьяна превышает норму на {deviation:.0f} ккал.")
        else:
            print(f"\nВывод: Татьяна отлично держит дефицит (в среднем {abs(deviation):.0f} ккал ниже нормы).")

if __name__ == "__main__":
    asyncio.run(calculate_tatiana_calories())
