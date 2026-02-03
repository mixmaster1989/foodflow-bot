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
    waiting_for_weight = State()
    waiting_for_confirmation = State()
    waiting_for_edit_value = State()


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
        base_name = result.get("base_name")
        
        # If weight is missing, ask user to specify
        if weight_missing:
            # Save context and ask for weight
            await state.update_data(
                pending_product={
                    "name": name,
                    "base_name": base_name,
                    "calories100": calories, 
                    "protein100": protein,
                    "fat100": fat,
                    "carbs100": carbs,
                    "fiber100": fiber
                }
            )
            await state.set_state(IAteStates.waiting_for_weight)
            
            builder = InlineKeyboardBuilder()
            builder.button(text="❌ Отмена", callback_data="main_menu")
            
            await status_msg.edit_text(
                f"🧐 Вы сказали: <i>{description}</i>\n"
                f"Это похоже на: <b>{name}</b>\n\n"
                f"⚖️ <b>Сколько грамм?</b> (Напишите число, например: 55)",
                parse_mode="HTML",
                reply_markup=builder.as_markup()
            )
            return

        # Happy path: Weight was detected
        await state.update_data(
            pending_product={
                "name": f"{name} ({weight_grams}г)",
                "base_name": base_name,
                "calories100": calories, 
                "protein100": protein,
                "fat100": fat,
                "carbs100": carbs,
                "fiber100": fiber
            }
        )
        
        # Instead of saving immediately, show confirmation
        await show_confirmation_interface(message, state, status_msg)
        
    except Exception as e:
        logger.error(f"Error in i_ate_process: {e}", exc_info=True)
        await state.clear()
        await status_msg.edit_text(f"❌ Ошибка: {e}\n\nПопробуйте ещё раз.")


@router.message(IAteStates.waiting_for_weight, F.text)
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
        
        # Update pending product with new weight
        # IMPORTANT: We DO NOT recalculate macros automatically here, as per user request.
        # User can edit them manually if needed.
        
        # FIX: Prevent double weight ("Apple (100g) (200g)")
        # Use base_name if available, otherwise try to strip existing weight
        if base_name:
             product['name'] = f"{base_name} ({int(weight)}г)"
        else:
             # Fallback: remove existing (...) from name
             clean_name = re.sub(r'\s*\(\d+г\)$', '', name)
             product['name'] = f"{clean_name} ({int(weight)}г)"
        
        # Updating state
        await state.update_data(pending_product=product)
        
        # Show confirmation
        await show_confirmation_interface(message, state)
        
    except Exception as e:
        logger.error(f"Weight Input Error: {e}", exc_info=True)
        await message.reply(f"❌ Ошибка: {e}")

# --- Helper Functions & New Handlers ---

async def show_confirmation_interface(message: types.Message, state: FSMContext, editable_message: types.Message = None):
    """Show the preview with Confirm/Edit buttons."""
    data = await state.get_data()
    product = data.get("pending_product")
    
    if not product:
        await message.reply("⚠️ Ошибка контекста.")
        return

    name = product.get('name')
    calories = product.get('calories100', 0) # Use the keys we store
    protein = product.get('protein100', 0)
    fat = product.get('fat100', 0)
    carbs = product.get('carbs100', 0)
    
    # Check if these are actually totals (from i_ate_process they are just values, mapped to 100 for storage sake? 
    # No, in i_ate_process we stored them as calories100 etc in the 'else' block, but as plain vars in the main block.
    # Let's standardize in i_ate_process before calling this function.
    # FIX: i_ate_process needs to save pending_product correctly in the 'happy path' too.
    # Wait, i_ate_process didn't save pending_product in the happy path (lines 122+).
    # I need to fix i_ate_process logic first in the ReplacementChunk above.
    
    # Standardizing display
    text = (
        f"🛡️ <b>Проверка данных</b>\n\n"
        f"🍽️ <b>{name}</b>\n\n"
        f"⚖️ Вес: <b>---</b> (текст)\n" # Hard to track weight separately if it's baked into name
        f"🔥 Ккал: <b>{int(calories)}</b>\n"
        f"🥩 Б: <b>{protein:.1f}</b> | 🥑 Ж: <b>{fat:.1f}</b> | 🍞 У: <b>{carbs:.1f}</b>"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Записать", callback_data="i_ate_confirm")
    builder.button(text="✏️ Ред. Вес", callback_data="edit_field_weight") # Simplified editing
    builder.button(text="✏️ Ред. КБЖУ", callback_data="i_ate_edit_macros")
    builder.button(text="❌ Отмена", callback_data="main_menu")
    builder.adjust(1, 2, 1)
    
    await state.set_state(IAteStates.waiting_for_confirmation)
    
    if editable_message:
        await editable_message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())


@router.callback_query(F.data == "i_ate_confirm", IAteStates.waiting_for_confirmation)
async def process_confirm(callback: types.CallbackQuery, state: FSMContext):
    """Save to DB."""
    data = await state.get_data()
    product = data.get("pending_product")
    
    async for session in get_db():
        log = ConsumptionLog(
            user_id=callback.from_user.id,
            product_name=product['name'],
            base_name=product.get('base_name'),
            calories=product.get('calories100'),
            protein=product.get('protein100'),
            fat=product.get('fat100'),
            carbs=product.get('carbs100'),
            fiber=product.get('fiber100', 0),
            date=datetime.utcnow()
        )
        session.add(log)
        await session.commit()
    
    await state.clear()
    
    # Format success message with full details
    calories = product.get('calories100', 0)
    protein = product.get('protein100', 0)
    fat = product.get('fat100', 0)
    carbs = product.get('carbs100', 0)
    
    success_text = (
        f"✅ <b>Записано!</b>\n\n"
        f"🍽️ {product['name']}\n\n"
        f"🔥 <b>{int(calories)}</b> ккал\n"
        f"🥩 {protein:.1f} | 🥑 {fat:.1f} | 🍞 {carbs:.1f}"
    )
    
    await callback.message.edit_text(success_text, parse_mode="HTML")
    # Show menu options again? Maybe just toast.

@router.callback_query(F.data == "edit_field_weight", IAteStates.waiting_for_confirmation)
async def start_edit_weight(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(IAteStates.waiting_for_weight) # Reuse existing logic
    await callback.message.edit_text("⚖️ Введите новый вес (числом):")

@router.callback_query(F.data == "i_ate_edit_macros", IAteStates.waiting_for_confirmation)
async def start_edit_macros(callback: types.CallbackQuery, state: FSMContext):
    builder = InlineKeyboardBuilder()
    builder.button(text="🔥 Ккал", callback_data="edit_macro_calories100")
    builder.button(text="🥩 Белки", callback_data="edit_macro_protein100")
    builder.button(text="🥑 Жиры", callback_data="edit_macro_fat100")
    builder.button(text="🍞 Углеводы", callback_data="edit_macro_carbs100")
    builder.button(text="🔙 Назад", callback_data="back_to_confirm")
    builder.adjust(2, 2, 1)
    
    await callback.message.edit_text("👇 Что меняем?", reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("edit_macro_"))
async def ask_macro_value(callback: types.CallbackQuery, state: FSMContext):
    field = callback.data.split("macro_")[1]
    await state.update_data(current_edit_field=field)
    await state.set_state(IAteStates.waiting_for_edit_value)
    
    labels = {
        "calories100": "Калории", "protein100": "Белки", 
        "fat100": "Жиры", "carbs100": "Углеводы"
    }
    
    await callback.message.edit_text(f"✏️ Введите новое значение для <b>{labels.get(field)}</b>:", parse_mode="HTML")

@router.message(IAteStates.waiting_for_edit_value)
async def save_macro_value(message: types.Message, state: FSMContext):
    try:
        value = float(message.text.split()[0].replace(',', '.'))
        data = await state.get_data()
        field = data.get("current_edit_field")
        product = data.get("pending_product")
        
        product[field] = value
        await state.update_data(pending_product=product)
        
        await show_confirmation_interface(message, state)
        
    except ValueError:
        await message.reply("⚠️ Введите число.")

@router.callback_query(F.data == "back_to_confirm")
async def back_to_confirm_handler(callback: types.CallbackQuery, state: FSMContext):
    await show_confirmation_interface(callback.message, state)
