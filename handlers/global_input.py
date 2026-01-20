"""Handler for global text input (when no state is active)."""
import logging
from datetime import datetime

from aiogram import Router, F, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from config import settings
from database.base import get_db
from database.models import Product, Receipt, ConsumptionLog, SavedDish
from services.normalization import NormalizationService
from services.ai import AIService # If needed, but NormalizationService covers most

router = Router()
logger = logging.getLogger(__name__)

class GlobalInputStates(StatesGroup):
    action_pending = State()
    waiting_for_weight = State()

@router.message(F.text, StateFilter(None))
async def handle_global_text(message: types.Message, state: FSMContext) -> None:
    """Catch-all for text messages when no state is active."""
    # Ignore commands (they are handled by other routers, assuming this router is last)
    if message.text.startswith("/"):
        return

    text = message.text.strip()
    if len(text) < 2:
        return # Ignore very short text

    # Save text to state
    await state.set_state(GlobalInputStates.action_pending)
    await state.update_data(global_text=text)

    builder = InlineKeyboardBuilder()
    builder.button(text="🍽️ Я съел", callback_data="global_action_ate")
    builder.button(text="🧊 В холодильник", callback_data="global_action_fridge")
    builder.button(text="❌ Отмена", callback_data="global_action_cancel")
    builder.adjust(2, 1)

    await message.reply(
        f"🤔 <b>Что сделать с этим?</b>\n\n"
        f"📝 <i>\"{text}\"</i>",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )

@router.callback_query(GlobalInputStates.action_pending, F.data == "global_action_cancel")
async def global_cancel(callback: types.CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.delete()
    await callback.answer("Отменено")

@router.callback_query(GlobalInputStates.action_pending, F.data == "global_action_ate")
async def global_i_ate(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Handle 'I ate' action for global text."""
    data = await state.get_data()
    text = data.get("global_text")
    
    if not text:
        await callback.answer("⚠️ Ошибка: текст потерян.", show_alert=True)
        await state.clear()
        return

    user_id = callback.from_user.id
    msg = callback.message
    
    await msg.edit_text(f"🔄 Анализирую: <i>{text}</i>...", parse_mode="HTML")
    
    try:
        # 1. Check Saved Dishes (Exact match first)
        dish_match = None
        async for session in get_db():
            stmt = select(SavedDish).where(SavedDish.user_id == user_id).where(SavedDish.name.ilike(text))
            res = await session.execute(stmt)
            dish_match = res.scalars().first()
            if dish_match:
                break
        
        if dish_match:
            # Use saved dish data
            name = dish_match.name
            calories = dish_match.total_calories
            protein = dish_match.total_protein
            fat = dish_match.total_fat
            carbs = dish_match.total_carbs
            fiber = dish_match.total_fiber
            weight_grams = None # It's a combo
            weight_missing = False
            base_name = name # Use dish name as base_name
            
            result = {} # Dummy
        else:
            # 2. AI Analysis
            result = await NormalizationService.analyze_food_intake(text)
            
            name = result.get("name", text)
            calories = float(result.get("calories") or 0)
            protein = float(result.get("protein") or 0)
            fat = float(result.get("fat") or 0)
            carbs = float(result.get("carbs") or 0)
            fiber = float(result.get("fiber") or 0)
            weight_grams = result.get("weight_grams")
            weight_missing = result.get("weight_missing", True)
            base_name = result.get("base_name")

            # If weight is missing (and it's not a saved dish where weight might be fixed)
            if weight_missing:
                # Save context and ask for weight
                await state.update_data(
                    pending_product={
                        "name": name,
                        "base_name": base_name,
                        "calories100": calories, # AI returns per 100g usually if weight missing
                        "protein100": protein,
                        "fat100": fat,
                        "carbs100": carbs,
                        "fiber100": fiber
                    }
                )
                await state.set_state(GlobalInputStates.waiting_for_weight)
                
                # Show AI guess but ask for weight
                await msg.edit_text(
                    f"🧐 Вы сказали: <i>{text}</i>\n"
                    f"Это похоже на: <b>{name}</b>\n\n"
                    f"⚖️ <b>Сколько грамм?</b> (Напишите число, например: 55)",
                    parse_mode="HTML"
                )
                return

        # Variables are now set from either SavedDish or AI Analysis (with weight)
        
        final_name = f"{name} ({weight_grams}г)" if weight_grams else name
        
        async for session in get_db():
            log = ConsumptionLog(
                user_id=user_id,
                product_name=final_name,
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
        
        # Success Message
        weight_note = "" if weight_grams else "\n⚠️ <i>Вес не указан, посчитано на 100г.</i>"
        
        await msg.edit_text(
            f"✅ <b>Записано!</b>\n\n"
            f"🍽️ {final_name}\n\n"
            f"🔥 <b>{int(calories)}</b> ккал\n"
            f"🥩 Белки: <b>{protein:.1f}</b>г\n"
            f"🥑 Жиры: <b>{fat:.1f}</b>г\n"
            f"🍞 Углеводы: <b>{carbs:.1f}</b>г\n"
            f"🥬 Клетчатка: <b>{fiber:.1f}</b>г{weight_note}",
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Global I Ate Error: {e}", exc_info=True)
        await msg.edit_text(f"❌ Ошибка: {e}")
        await state.clear()


@router.message(GlobalInputStates.waiting_for_weight, F.text)
async def handle_weight_input(message: types.Message, state: FSMContext) -> None:
    """Handle weight input (e.g., '55') after manual entry."""
    try:
        weight_text = message.text.replace(',', '.').strip()
        # Extract number if mixed text (e.g. "55g")
        import re
        match = re.search(r'(\d+(?:\.\d+)?)', weight_text)
        
        if not match:
            await message.reply("⚠️ Пожалуйста, введите только число (вес в граммах).")
            return

        weight = float(match.group(1))
        
        data = await state.get_data()
        product = data.get("pending_product")
        
        if not product:
            await message.reply("⚠️ Ошибка контекста. Попробуйте ввести продукт заново.")
            await state.clear()
            return
            
        # Recalculate based on weight
        factor = weight / 100.0
        
        name = product['name']
        base_name = product['base_name']
        calories = product['calories100'] * factor
        protein = product['protein100'] * factor
        fat = product['fat100'] * factor
        carbs = product['carbs100'] * factor
        fiber = product['fiber100'] * factor
        
        final_name = f"{name} ({int(weight)}г)"
        
        async for session in get_db():
            log = ConsumptionLog(
                user_id=message.from_user.id,
                product_name=final_name,
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
        
        await message.answer(
            f"✅ <b>Записано!</b>\n\n"
            f"🍽️ {final_name}\n\n"
            f"🔥 <b>{int(calories)}</b> ккал\n"
            f"🥩 Белки: <b>{protein:.1f}</b>г\n"
            f"🥑 Жиры: <b>{fat:.1f}</b>г\n"
            f"🍞 Углеводы: <b>{carbs:.1f}</b>г\n"
            f"🥬 Клетчатка: <b>{fiber:.1f}</b>г",
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Weight Input Error: {e}", exc_info=True)
        await message.reply(f"❌ Ошибка при сохранении: {e}")
        await state.clear()
        
    except Exception as e:
        logger.error(f"Global I Ate Error: {e}", exc_info=True)
        await msg.edit_text(f"❌ Ошибка: {e}")
        await state.clear()

@router.callback_query(GlobalInputStates.action_pending, F.data == "global_action_fridge")
async def global_fridge(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Handle 'To Fridge' action for global text."""
    data = await state.get_data()
    text = data.get("global_text")
    
    if not text:
        await callback.answer("⚠️ Ошибка: текст потерян.", show_alert=True)
        await state.clear()
        return

    user_id = callback.from_user.id
    msg = callback.message
    
    await msg.edit_text(f"🔄 Добавляю в холодильник: <i>{text}</i>...", parse_mode="HTML")
    
    try:
        # AI Analysis (Same service, but we use it for Product fields)
        result = await NormalizationService.analyze_food_intake(text)
        
        name = result.get("name", text)
        calories = float(result.get("calories") or 0)
        protein = float(result.get("protein") or 0)
        fat = float(result.get("fat") or 0)
        carbs = float(result.get("carbs") or 0)
        fiber = float(result.get("fiber") or 0)
        weight_grams = result.get("weight_grams")
        
        
        async for session in get_db():
            product = Product(
                user_id=user_id,
                name=name,
                category="Manual", # Unknown category
                calories=calories,
                protein=protein,
                fat=fat,
                carbs=carbs,
                fiber=fiber,
                price=0.0,
                quantity=1.0, 
                weight_g=float(weight_grams) if weight_grams else 100.0, # Default to 100g if weight missing? Or None?
                source="global_text"
            )
            session.add(product)
            await session.commit()
            
        await state.clear()
        
        await msg.edit_text(
            f"✅ <b>Добавлено в холодильник!</b>\n\n"
            f"📦 {name}\n"
            f"⚖️ {weight_grams if weight_grams else '100'}г",
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Global Fridge Error: {e}", exc_info=True)
        await msg.edit_text(f"❌ Ошибка: {e}")
        await state.clear()
