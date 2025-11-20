from aiogram import Router, F, types
from sqlalchemy import select, func
from datetime import datetime, timedelta
from FoodFlow.database.base import get_db
from FoodFlow.database.models import ConsumptionLog

router = Router()

@router.message(F.text == "📊 Статистика")
async def show_stats(message: types.Message):
    user_id = message.from_user.id
    today = datetime.utcnow().date()
    
    async for session in get_db():
        # Get today's consumption
        stmt = select(ConsumptionLog).where(
            ConsumptionLog.user_id == user_id,
            func.date(ConsumptionLog.date) == today
        )
        logs = (await session.execute(stmt)).scalars().all()
        
        if not logs:
            await message.answer(
                "📊 <b>Статистика за сегодня</b>\n\n"
                "Пока нет данных.\n"
                "Нажми 🍽️ на продукты в холодильнике, чтобы отметить что съел!",
                parse_mode="HTML"
            )
            return
        
        # Calculate totals
        total_calories = sum(log.calories for log in logs)
        total_protein = sum(log.protein for log in logs)
        total_fat = sum(log.fat for log in logs)
        total_carbs = sum(log.carbs for log in logs)
        
        # Build response
        response = (
            f"📊 <b>Твоя статистика за сегодня</b>\n\n"
            f"🔥 Калории: <b>{total_calories:.0f}</b> ккал\n"
            f"🥩 Белки: <b>{total_protein:.1f}</b>г\n"
            f"🥑 Жиры: <b>{total_fat:.1f}</b>г\n"
            f"🍞 Углеводы: <b>{total_carbs:.1f}</b>г\n\n"
            f"📝 Приёмов пищи: <b>{len(logs)}</b>\n\n"
            f"<b>Последние:</b>\n"
        )
        
        for log in logs[-5:]:
            response += f"▫️ {log.product_name} ({log.calories:.0f}ккал)\n"
        
        await message.answer(response, parse_mode="HTML")
        break
