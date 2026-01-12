"""Handler for quick food logging via text description."""
import logging
from datetime import datetime

from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import settings
from database.base import get_db
from database.models import ConsumptionLog
from services.normalization import NormalizationService

router = Router()
logger = logging.getLogger(__name__)


class IAteStates(StatesGroup):
    waiting_for_description = State()


@router.callback_query(F.data == "menu_i_ate")
async def i_ate_start(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Start the 'I ate' flow - ask for food description."""
    await state.set_state(IAteStates.waiting_for_description)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="main_menu")
    
    text = (
        "🍽️ <b>Что съели?</b>\n\n"
        "Опишите что вы съели и примерный размер порции.\n\n"
        "<i>Например:\n"
        "• Тарелка борща\n"
        "• Куриная грудка 200г с рисом\n"
        "• 2 яйца и тост с авокадо\n"
        "• Большая порция пасты карбонара</i>"
    )
    
    try:
        await callback.message.edit_caption(caption=text, parse_mode="HTML", reply_markup=builder.as_markup())
    except Exception:
        try:
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
        except Exception:
            await callback.message.delete()
            await callback.message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()


@router.message(IAteStates.waiting_for_description)
async def i_ate_process(message: types.Message, state: FSMContext) -> None:
    """Process food description, get KBJU from AI, save to consumption log."""
    description = message.text.strip()
    user_id = message.from_user.id
    
    status_msg = await message.answer("🔄 Анализирую...")
    
    try:
        # Use NormalizationService to get KBJU
        normalizer = NormalizationService()
        
        # Format as a single item for normalization
        result = await normalizer.normalize_products([{"name": description}])
        
        if result and len(result) > 0:
            item = result[0]
            name = item.get("name", description)
            calories = float(item.get("calories") or 0)
            protein = float(item.get("protein") or 0)
            fat = float(item.get("fat") or 0)
            carbs = float(item.get("carbs") or 0)
            fiber = float(item.get("fiber") or 0)
        else:
            # Fallback if AI fails
            name = description
            calories = 300  # Default estimate
            protein = 15
            fat = 10
            carbs = 35
            fiber = 2
        
        # Save to consumption log
        async for session in get_db():
            log = ConsumptionLog(
                user_id=user_id,
                product_name=name,
                calories=calories,
                protein=protein,
                fat=fat,
                carbs=carbs,
                fiber=fiber,
                date=datetime.utcnow()
            )
            session.add(log)
            await session.commit()
        
        await state.clear()
        
        builder = InlineKeyboardBuilder()
        builder.button(text="🍽️ Ещё поел", callback_data="menu_i_ate")
        builder.button(text="📊 Статистика", callback_data="menu_stats")
        builder.button(text="🏠 Меню", callback_data="main_menu")
        builder.adjust(1, 2)
        
        response = (
            f"✅ <b>Записано!</b>\n\n"
            f"🍽️ {name}\n\n"
            f"🔥 <b>{int(calories)}</b> ккал\n"
            f"🥩 Белки: <b>{protein:.1f}</b>г\n"
            f"🥑 Жиры: <b>{fat:.1f}</b>г\n"
            f"🍞 Углеводы: <b>{carbs:.1f}</b>г\n"
            f"🥬 Клетчатка: <b>{fiber:.1f}</b>г"
        )
        
        await status_msg.edit_text(response, parse_mode="HTML", reply_markup=builder.as_markup())
        
    except Exception as e:
        logger.error(f"Error in i_ate_process: {e}", exc_info=True)
        await state.clear()
        
        builder = InlineKeyboardBuilder()
        builder.button(text="🔄 Попробовать снова", callback_data="menu_i_ate")
        builder.button(text="🏠 Меню", callback_data="main_menu")
        builder.adjust(1)
        
        await status_msg.edit_text(
            f"❌ Ошибка: {e}\n\nПопробуйте ещё раз или опишите еду иначе.",
            reply_markup=builder.as_markup()
        )
