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
    builder.button(text="⭐ Мои блюда", callback_data="menu_saved_dishes")
    builder.button(text="🍽️ Приёмы пищи", callback_data="menu_saved_meals")
    builder.button(text="🏗️ Собрать блюдо", callback_data="menu_build_dish")
    builder.button(text="🍳 Собрать приём", callback_data="menu_build_meal")
    builder.button(text="❌ Отмена", callback_data="main_menu")
    builder.adjust(2, 2, 1)
    
    caption = (
        "🍽️ <b>Что съели?</b>\n\n"
        "Опишите что вы съели <b>с указанием веса</b>.\n\n"
        "<i>Например:\n"
        "• Борщ 300г\n"
        "• Куриная грудка 200г\n"
        "• 2 яйца</i>"
    )
    
    photo_path = types.FSInputFile("assets/i_ate.png")
    
    try:
        await callback.message.edit_media(
            media=types.InputMediaPhoto(media=photo_path, caption=caption, parse_mode="HTML"),
            reply_markup=builder.as_markup()
        )
    except Exception:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer_photo(
            photo=photo_path,
            caption=caption,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    await callback.answer()


@router.message(IAteStates.waiting_for_description)
async def i_ate_process(message: types.Message, state: FSMContext) -> None:
    """Process food description, get KBJU from AI, save to consumption log."""
    description = message.text or message.caption
    if not description:
        await message.answer("⚠️ Пожалуйста, напишите название блюда текстом (или отправьте фото с описанием).")
        return
        
    description = description.strip()
    user_id = message.from_user.id
    
    status_msg = await message.answer("🔄 Анализирую...")
    
    try:
        # Use new analyze_food_intake method with weight detection
        result = await NormalizationService.analyze_food_intake(description)
        
        name = result.get("name", description)
        calories = float(result.get("calories") or 0)
        protein = float(result.get("protein") or 0)
        fat = float(result.get("fat") or 0)
        carbs = float(result.get("carbs") or 0)
        fiber = float(result.get("fiber") or 0)
        weight_grams = result.get("weight_grams")
        weight_missing = result.get("weight_missing", True)
        
        # If weight is missing, ask user to specify
        if weight_missing:
            builder = InlineKeyboardBuilder()
            builder.button(text="🍽️ Ещё раз", callback_data="menu_i_ate")
            builder.button(text="🏠 Меню", callback_data="main_menu")
            builder.adjust(2)
            
            await status_msg.edit_text(
                f"⚠️ <b>Не указан вес!</b>\n\n"
                f"Найдено: <b>{name}</b>\n"
                f"КБЖУ на 100г: {int(calories)} ккал / {protein:.1f}б / {fat:.1f}ж / {carbs:.1f}у\n\n"
                f"📏 <b>Укажите вес в граммах</b>, чтобы записать точные данные.\n\n"
                f"<i>Например: {name} 150г</i>",
                parse_mode="HTML",
                reply_markup=builder.as_markup()
            )
            # Don't clear state - let user try again
            return
        
        base_name = result.get("base_name")
        
        # Save to consumption log (weight was detected)
        async for session in get_db():
            log = ConsumptionLog(
                user_id=user_id,
                product_name=f"{name} ({weight_grams}г)" if weight_grams else name,
                base_name=base_name,
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
        builder.button(text="🍽️ Ещё", callback_data="menu_i_ate")
        builder.button(text="📊 Статистика", callback_data="menu_stats")
        builder.button(text="🏠 Меню", callback_data="main_menu")
        builder.adjust(1, 2)
        
        weight_text = f" ({weight_grams}г)" if weight_grams else ""
        response = (
            f"✅ <b>Записано!</b>\n\n"
            f"🍽️ {name}{weight_text}\n\n"
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
        builder.button(text="⭐ Мои блюда", callback_data="menu_saved_dishes") # Placeholder for future list
        builder.button(text="🏗️ Собрать блюдо", callback_data="menu_build_dish") 
        builder.button(text="🏠 Меню", callback_data="main_menu")
        builder.adjust(1)
        
        await status_msg.edit_text(
            f"❌ Ошибка: {e}\n\nПопробуйте ещё раз или опишите еду иначе.",
            reply_markup=builder.as_markup()
        )
