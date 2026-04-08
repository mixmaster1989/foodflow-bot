import asyncio
import json
import logging
import os
import sys
from datetime import datetime

# Добавляем путь к корню проекта
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from database.base import get_db
from database.models import User, UserSettings, ConsumptionLog, WaterLog, WeightLog, Subscription

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Список ID целевых пользователей (женщины)
TARGET_IDS = [
    5263406733, 295543071, 495294354, 911990304, 7846721167,
    5422141137, 109153550, 104202119, 7899005241, 1044916834,
    7206006611, 5153798702, 5204589721
]

def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError ("Type %s not serializable" % type(obj))

async def get_user_full_data(session, user_id):
    """Сбор всех данных по одному пользователю."""
    data = {"user_id": user_id}
    
    # 1. Основной профиль и настройки
    stmt_user = select(User).where(User.id == user_id)
    user = (await session.execute(stmt_user)).scalar_one_or_none()
    if not user:
        return None
        
    data["profile"] = {
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "role": user.role,
        "created_at": user.created_at
    }
    
    stmt_settings = select(UserSettings).where(UserSettings.user_id == user_id)
    settings = (await session.execute(stmt_settings)).scalar_one_or_none()
    if settings:
        data["settings"] = {
            "gender": settings.gender,
            "age": settings.age,
            "height": settings.height,
            "weight": settings.weight,
            "goal": settings.goal,
            "calorie_goal": settings.calorie_goal,
            "protein_goal": settings.protein_goal,
            "fat_goal": settings.fat_goal,
            "carb_goal": settings.carb_goal,
            "fiber_goal": settings.fiber_goal,
            "water_goal": settings.water_goal,
            "allergies": settings.allergies,
            "is_initialized": settings.is_initialized
        }
    
    # 2. Логи питания (все)
    stmt_cons = select(ConsumptionLog).where(ConsumptionLog.user_id == user_id).order_by(ConsumptionLog.date)
    cons_logs = (await session.execute(stmt_cons)).scalars().all()
    data["consumption_logs"] = [
        {
            "product": log.product_name,
            "calories": log.calories,
            "protein": log.protein,
            "fat": log.fat,
            "carbs": log.carbs,
            "fiber": log.fiber,
            "date": log.date
        } for log in cons_logs
    ]
    
    # 3. Логи воды
    stmt_water = select(WaterLog).where(WaterLog.user_id == user_id).order_by(WaterLog.date)
    water_logs = (await session.execute(stmt_water)).scalars().all()
    data["water_logs"] = [
        {"amount_ml": log.amount_ml, "date": log.date} for log in water_logs
    ]
    
    # 4. Логи веса
    stmt_weight = select(WeightLog).where(WeightLog.user_id == user_id).order_by(WeightLog.recorded_at)
    weight_logs = (await session.execute(stmt_weight)).scalars().all()
    data["weight_logs"] = [
        {"weight": log.weight, "date": log.recorded_at} for log in weight_logs
    ]
    
    # 5. Подписка
    stmt_sub = select(Subscription).where(Subscription.user_id == user_id)
    sub = (await session.execute(stmt_sub)).scalar_one_or_none()
    if sub:
        data["subscription"] = {
            "tier": sub.tier,
            "starts_at": sub.starts_at,
            "expires_at": sub.expires_at,
            "is_active": sub.is_active,
            "auto_renew": sub.auto_renew
        }
        
    return data

async def main():
    logger.info("🔍 Начинаю экспорт полной статистики пользователей...")
    all_data = []
    
    # Создаем папку data, если её нет
    os.makedirs("data", exist_ok=True)
    
    async for session in get_db():
        for user_id in TARGET_IDS:
            logger.info(f"обработка пользователя {user_id}...")
            user_data = await get_user_full_data(session, user_id)
            if user_data:
                all_data.append(user_data)
        break # Выход из генератора сессии
        
    output_path = "data/march_8_stats.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2, default=json_serial)
    
    logger.info(f"✅ Экспорт завершен. Данные сохранены в {output_path}")
    logger.info(f"Всего обработано пользователей: {len(all_data)}")

if __name__ == "__main__":
    asyncio.run(main())
