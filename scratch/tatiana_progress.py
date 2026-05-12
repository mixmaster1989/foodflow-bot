
import asyncio

from sqlalchemy import asc, select

from database.base import get_db
from database.models import User, UserSettings, WeightLog


async def run_tatiana_report():
    user_id = 5153798702
    async for session in get_db():
        # 1. Данные пользователя и настройки
        user_stmt = select(User).where(User.id == user_id)
        user = (await session.execute(user_stmt)).scalar_one_or_none()

        settings_stmt = select(UserSettings).where(UserSettings.user_id == user_id)
        settings = (await session.execute(settings_stmt)).scalar_one_or_none()

        # 2. Логи веса
        weight_stmt = select(WeightLog).where(WeightLog.user_id == user_id).order_by(asc(WeightLog.recorded_at))
        weights = (await session.execute(weight_stmt)).scalars().all()

        print("--- Отчет по прогрессу: Татьяна Безручкина ---")
        if user:
            print(f"Дата регистрации: {user.created_at.strftime('%Y-%m-%d')}")

        if settings:
            goal_names = {
                "lose_weight": "Похудение",
                "maintain": "Поддержание",
                "healthy": "Здоровье",
                "gain_mass": "Набор массы"
            }
            print(f"Цель: {goal_names.get(settings.goal, settings.goal)}")
            print(f"Целевые калории: {settings.calorie_goal} ккал")

        print("\nДинамика веса:")
        if not weights:
            print("  Замеров веса не найдено.")
        else:
            start_weight = weights[0].weight
            current_weight = weights[-1].weight
            diff = current_weight - start_weight

            for w in weights:
                print(f"  [{w.recorded_at.strftime('%Y-%m-%d %H:%M')}] {w.weight} кг")

            print("\nИТОГО:")
            print(f"  Стартовый вес: {start_weight} кг")
            print(f"  Текущий вес: {current_weight} кг")

            if diff < 0:
                print(f"  Результат: Сброшено {abs(diff):.1f} кг 📉 (Молодец!)")
            elif diff > 0:
                print(f"  Результат: Набрано {diff:.1f} кг 📈")
            else:
                print("  Результат: Вес стабилен ⚖️")

if __name__ == "__main__":
    asyncio.run(run_tatiana_report())
