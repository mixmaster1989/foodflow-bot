
import asyncio
from datetime import datetime, timedelta

from sqlalchemy import func, select

from database.base import get_db
from database.models import ConsumptionLog, User, UserSettings, WaterLog, WeightLog


async def run_report():
    print("--- Отчет по активности FoodFlow (последние 7 дней) ---\n")

    last_week = datetime.now() - timedelta(days=7)

    async for session in get_db():
        # 1. Общая статистика
        total_users = (await session.execute(select(func.count(User.id)))).scalar()
        new_users = (await session.execute(select(User).where(User.created_at >= last_week))).scalars().all()

        print(f"Всего пользователей в базе: {total_users}")
        print(f"Новых за неделю: {len(new_users)}")
        for u in new_users:
            print(f"  - @{u.username or 'N/A'} ({u.first_name or ''} {u.last_name or ''}) от {u.created_at.strftime('%Y-%m-%d')}")

        # 2. Активные пользователи (кто что-то логировал)
        print("\nАктивность за неделю (логи еды/воды/веса):")

        # Еда
        food_active = (await session.execute(
            select(User.id, User.username, User.first_name, User.last_name, func.count(ConsumptionLog.id))
            .join(ConsumptionLog, User.id == ConsumptionLog.user_id)
            .where(ConsumptionLog.date >= last_week)
            .group_by(User.id)
        )).all()

        if food_active:
            for row in food_active:
                print(f"  🍎 {row[2]} {row[3]} (@{row[1]}): {row[4]} записей еды")
        else:
            print("  (Записей еды нет)")

        # Вода
        water_active = (await session.execute(
            select(User.id, User.username, User.first_name, User.last_name, func.count(WaterLog.id))
            .join(WaterLog, User.id == WaterLog.user_id)
            .where(WaterLog.date >= last_week)
            .group_by(User.id)
        )).all()

        if water_active:
            for row in water_active:
                print(f"  💧 {row[2]} {row[3]} (@{row[1]}): {row[4]} записей воды")

        # Вес
        weight_active = (await session.execute(
            select(User.id, User.username, User.first_name, User.last_name, func.count(WeightLog.id))
            .join(WeightLog, User.id == WeightLog.user_id)
            .where(WeightLog.recorded_at >= last_week)
            .group_by(User.id)
        )).all()

        if weight_active:
            for row in weight_active:
                print(f"  ⚖️ {row[2]} {row[3]} (@{row[1]}): {row[4]} замера веса")

        # 3. Поиск Татьяны Безручкиной
        print("\nПоиск Татьяны Безручкиной:")
        tatyana = (await session.execute(
            select(User).where(User.first_name.like("%Татьяна%"))
        )).scalars().all()

        if tatyana:
            for t in tatyana:
                # Get her settings
                s_stmt = select(UserSettings).where(UserSettings.user_id == t.id)
                settings = (await session.execute(s_stmt)).scalar_one_or_none()
                init_status = "Инициализирован" if settings and settings.is_initialized else "НЕ инициализирован"
                print(f"  Найдена: {t.first_name} {t.last_name} (@{t.username})")
                print(f"    - ID: {t.id}")
                print(f"    - Статус: {init_status}")
                print(f"    - Последняя активность: {t.last_activity}")
        else:
            print("  Татьяна Безручкина не найдена по имени.")

if __name__ == "__main__":
    asyncio.run(run_report())
