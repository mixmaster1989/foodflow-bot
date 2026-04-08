import logging
from aiogram import Router, types
from aiogram.filters import Command, StateFilter
from sqlalchemy import select
from database.base import get_db
from database.models import CanonicalProduct
from config import settings

router = Router()
logger = logging.getLogger(__name__)

@router.message(Command("etalon"), StateFilter("*"))
async def cmd_etalon_list(message: types.Message):
    """Show list of verified etalon products for pilot users."""
    if message.from_user.id not in settings.PILOT_USER_IDS:
        # Silently ignore if not in pilot group to avoid command pollution for others
        return

    try:
        async for session in get_db():
            stmt = select(CanonicalProduct).where(CanonicalProduct.is_verified == True).order_by(CanonicalProduct.base_name)
            result = await session.execute(stmt)
            products = result.scalars().all()
            
            if not products:
                await message.answer("📭 В базе эталонов пока пусто.")
                return

            text = "💎 <b>Список эталонных продуктов (на 100г):</b>\n\n"
            for p in products:
                text += f"• <b>{p.base_name.capitalize()}</b>: {int(p.calories)} ккал ({p.protein}Б/{p.fat}Ж/{p.carbs}У)\n"
            
            text += "\n<i>Эти продукты распознаются мгновенно и с гарантированной точностью.</i>"
            
            # Divide long messages if needed
            if len(text) > 4000:
                parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
                for part in parts:
                    await message.answer(part, parse_mode="HTML")
            else:
                await message.answer(text, parse_mode="HTML")
            break
            
    except Exception as e:
        logger.error(f"Error in /etalon command: {e}")
        await message.answer("❌ Ошибка при получении списка.")
