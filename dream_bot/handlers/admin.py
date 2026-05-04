from aiogram import Router, types
from aiogram.filters import Command
from sqlalchemy import select, func
from database.base import SessionLocal
from database.models import User, DreamLog

router = Router()

@router.message(Command("stats"))
async def cmd_stats(message: types.Message):
    async with SessionLocal() as session:
        user = await session.get(User, message.from_user.id)
        if not user or not user.is_admin:
            # Скрытая команда для админа
            return

        # Общая статистика
        total_users = (await session.execute(select(func.count(User.id)))).scalar()
        total_dreams = (await session.execute(select(func.count(DreamLog.id)))).scalar()
        
        usage_stats = (await session.execute(
            select(
                func.sum(DreamLog.prompt_tokens),
                func.sum(DreamLog.completion_tokens),
                func.sum(DreamLog.cost_usd)
            )
        )).fetchone()

        p_tokens = usage_stats[0] or 0
        c_tokens = usage_stats[1] or 0
        total_micro_usd = usage_stats[2] or 0
        total_usd = total_micro_usd / 1000000

        stats_text = (
            "📊 <b>Статистика Оракула</b>\n\n"
            f"👤 Всего пользователей: <b>{total_users}</b>\n"
            f"🔮 Всего толкований: <b>{total_dreams}</b>\n\n"
            "💰 <b>Затраты ИИ:</b>\n"
            f"📥 Входящие токены: <code>{p_tokens}</code>\n"
            f"📤 Исходящие токены: <code>{c_tokens}</code>\n"
            f"💵 Итого потрачено: <b>${total_usd:.4f}</b>"
        )
        await message.answer(stats_text, parse_mode="HTML")
