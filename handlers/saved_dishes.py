import logging
import json
from collections import Counter
from datetime import datetime

from aiogram import Router, F, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, desc

from database.base import get_db
from database.models import ConsumptionLog, SavedDish

router = Router()
logger = logging.getLogger(__name__)

class SavedDishStates(StatesGroup):
    building_dish = State() # Selecting components for dish
    naming_dish = State()   # Entering dish name
    building_meal = State() # Selecting dishes+products for meal
    naming_meal = State()   # Entering meal name

# --- Entry Point: Build Dish ---
# --- Entry Point: Build Dish ---
@router.callback_query(F.data == "menu_build_dish")
async def start_build_dish(callback: types.CallbackQuery, state: FSMContext):
    """Start the interactive flow to build a saved dish."""
    await state.clear()
    
    await state.set_state(SavedDishStates.building_dish)
    await state.update_data(
        dish_components=[],
        total_stats={"cal": 0, "prot": 0, "fat": 0, "carb": 0, "fib": 0}
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="main_menu")
    
    text = (
        "🏗️ <b>Конструктор Блюда</b>\n\n"
        "Давайте соберем блюдо по ингредиентам.\n"
        "Напишите <b>первый ингредиент</b> (например: <i>Хлеб 40г</i>)"
    )
    
    try:
        await callback.message.edit_text(
            text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    except Exception:
        # If we can't edit (e.g. it was a photo), delete and send new
        await callback.message.delete()
        await callback.message.answer(
            text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    await callback.answer()

@router.message(SavedDishStates.building_dish, F.text)
async def process_ingredient_input(message: types.Message, state: FSMContext):
    """Handle text input for ingredients."""
    text = message.text.strip()
    
    # Analyze text
    from services.normalization import NormalizationService
    
    # Using NormalizationService to get data
    # Note: We rely on it to handle "Bread 40g" and return parsed weight
    msg = await message.answer(f"🔄 Добавляю: <i>{text}</i>...", parse_mode="HTML")
    
    try:
        result = await NormalizationService.analyze_food_intake(text)
        
        name = result.get("name", text)
        calories = float(result.get("calories") or 0)
        protein = float(result.get("protein") or 0)
        fat = float(result.get("fat") or 0)
        carbs = float(result.get("carbs") or 0)
        fiber = float(result.get("fiber") or 0)
        weight_grams = result.get("weight_grams")
        
        if not weight_grams:
             # FALLBACK 1: Try Regex locally
             import re
             match = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:г|гр|грамм|g|ml|мл)?', text, re.IGNORECASE)
             if match:
                 try:
                     weight_grams = float(match.group(1).replace(',', '.'))
                     # Recalculate stats based on new weight vs 100g base
                     # The AI usually returns stats per 100g if weight is missing
                     factor = weight_grams / 100.0
                     calories = calories * factor # Note: AI might have returned 100g stats
                     protein = protein * factor
                     fat = fat * factor
                     carbs = carbs * factor
                     fiber = fiber * factor
                 except:
                     pass

        if not weight_grams:
             # If still missing after regex, ask user
             await msg.edit_text(
                 f"⚠️ <b>{name}</b>: Не понял вес.\n"
                 "Пожалуйста, напишите с весом, например: <i>Хлеб 40г</i>"
             )
             return

        # Add to state
        data = await state.get_data()
        components = data.get("dish_components", [])
        stats = data.get("total_stats", {"cal": 0, "prot": 0, "fat": 0, "carb": 0, "fib": 0})
        
        # New component
        comp = {
            "name": name,
            "base_name": result.get("base_name", name),
            "weight": weight_grams,
            "calories": calories,
            "protein": protein,
            "fat": fat,
            "carbs": carbs,
            "fiber": fiber
        }
        components.append(comp)
        
        # Update totals
        stats["cal"] += calories
        stats["prot"] += protein
        stats["fat"] += fat
        stats["carb"] += carbs
        stats["fib"] += fiber
        
        await state.update_data(dish_components=components, total_stats=stats)
        
        # Render list
        comp_list = "\n".join([f"• {c['name']} ({c['weight']}г) - {int(c['calories'])} ккал" for c in components])
        
        builder = InlineKeyboardBuilder()
        builder.button(text="✅ Закончить и назвать", callback_data="dish_finish_building")
        builder.button(text="❌ Отмена", callback_data="main_menu")
        builder.adjust(1)
        
        await msg.edit_text(
            f"🏗️ <b>Блюдо собирается...</b>\n\n"
            f"{comp_list}\n\n"
            f"<b>Итого:</b> {int(stats['cal'])} ккал\n"
            f"🥩 {stats['prot']:.1f} | 🥑 {stats['fat']:.1f} | 🍞 {stats['carb']:.1f} | 🥬 {stats['fib']:.1f}\n\n"
            f"👇 <b>Что дальше?</b> (Напишите следующий ингредиент или нажмите 'Закончить')",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Ingredient Add Error: {e}", exc_info=True)
        await msg.edit_text(f"❌ Ошибка: {e}")

@router.callback_query(SavedDishStates.building_dish, F.data == "dish_finish_building")
async def finish_building_dish(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    components = data.get("dish_components", [])
    
    if not components:
        await callback.answer("Сначала добавьте ингредиенты!", show_alert=True)
        return

    # Generate suggestion
    from services.normalization import NormalizationService
    ing_names = [c['name'] for c in components]
    
    # Show loading status
    try:
        await callback.message.edit_text("🤖 <i>Придумываю название...</i>", parse_mode="HTML")
    except Exception:
        await callback.message.delete()
        await callback.message.answer("🤖 <i>Придумываю название...</i>", parse_mode="HTML")

    suggested_name = await NormalizationService.suggest_dish_name(ing_names)
    
    await state.set_state(SavedDishStates.naming_dish)
    await state.update_data(suggested_name=suggested_name)
    
    builder = InlineKeyboardBuilder()
    builder.button(text=f"🏷️ {suggested_name}", callback_data="dish_use_suggestion")
    builder.button(text="❌ Отмена", callback_data="main_menu")
    builder.adjust(1)

    text = (
        f"📝 <b>Как назовем блюдо?</b>\n\n"
        f"Я предлагаю: <b>{suggested_name}</b>\n"
        f"Нажмите кнопку ниже или напишите свое название."
    )
    
    try:
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        
    await callback.answer()

@router.callback_query(SavedDishStates.naming_dish, F.data == "dish_use_suggestion")
async def use_suggested_name(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    name = data.get("suggested_name", "Мое блюдо")
    await save_dish_internal(callback.message, state, name)
    await callback.answer()

@router.callback_query(SavedDishStates.building_dish, F.data.startswith("dish_toggle:"))
async def on_toggle(callback: types.CallbackQuery, state: FSMContext):
    # Backward compatibility: No-op for new interactive builder
    await callback.answer()

async def save_dish_internal(message: types.Message, state: FSMContext, name: str):
    """Shared save logic for text input and button click."""
    data = await state.get_data()
    # Try to get user_id from message or from state if message is tricky (callback message)
    user_id = message.chat.id 

    status_msg = await message.answer(f"💾 Сохраняю <b>{name}</b>...", parse_mode="HTML")
    
    components = []
    total_cal = 0.0
    total_prot = 0.0
    total_fat = 0.0
    total_carb = 0.0
    total_fib = 0.0
    
    if "dish_components" in data:
        raw_components = data["dish_components"]
        for c in raw_components:
            components.append({
                "name": c["name"],
                "base_name": c["base_name"],
                "calories": c["calories"],
                "protein": c["protein"],
                "fat": c["fat"],
                "carbs": c["carbs"],
                "fiber": c.get("fiber", 0)
            })
            total_cal += c["calories"]
            total_prot += c["protein"]
            total_fat += c["fat"]
            total_carb += c["carbs"]
            total_fib += c.get("fiber", 0)
    
    # Save to DB
    async for session in get_db():
        new_dish = SavedDish(
            user_id=user_id,
            name=name,
            components=components,
            total_calories=total_cal,
            total_protein=total_prot,
            total_fat=total_fat,
            total_carbs=total_carb,
            total_fiber=total_fib
        )
        session.add(new_dish)
        await session.commit()

    await state.clear()
    
    # Format components list
    comp_text = "\n".join([f"• {c.get('name', c.get('base_name', '?'))}" for c in components])
    
    await status_msg.edit_text(
        f"✅ <b>Блюдо сохранено!</b>\n\n"
        f"🥪 <b>{name}</b>\n\n"
        f"🔥 <b>{int(total_cal)}</b> ккал\n"
        f"🥩 Белки: <b>{total_prot:.1f}</b>г\n"
        f"🥑 Жиры: <b>{total_fat:.1f}</b>г\n"
        f"🍞 Углеводы: <b>{total_carb:.1f}</b>г\n"
        f"🥬 Клетчатка: <b>{total_fib:.1f}</b>г\n\n"
        f"<b>Состав:</b>\n{comp_text}\n\n"
        f"Теперь просто пишите <i>\"{name}\"</i> в чат!",
        parse_mode="HTML"
    )

@router.callback_query(SavedDishStates.building_dish, F.data == "dish_prev")
async def on_prev(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    p = data.get("current_page", 0)
    if p > 0:
        await state.update_data(current_page=p-1)
        await render_builder_ui(callback.message, state)
    await callback.answer()

@router.callback_query(SavedDishStates.building_dish, F.data == "dish_next")
async def on_next(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.update_data(current_page=data.get("current_page", 0)+1)
    await render_builder_ui(callback.message, state)
    await callback.answer()

@router.callback_query(SavedDishStates.building_dish, F.data == "dish_ask_name")
async def ask_dish_name(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(SavedDishStates.naming_dish)
    await callback.message.edit_text(
        "📝 <b>Как назовем это блюдо?</b>\n\n"
        "Пришлите название (например: <i>Мой Завтрак</i>, <i>Супер Бутер</i>).",
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(SavedDishStates.building_dish, F.data == "dish_noop")
async def noop(callback: types.CallbackQuery):
    await callback.answer("Сначала выберите продукты!")

@router.message(SavedDishStates.naming_dish, F.text)
async def save_dish_final(message: types.Message, state: FSMContext):
    name = message.text.strip()
    await save_dish_internal(message, state, name)

# =====================================================
# "Мои блюда" - List View
# =====================================================

@router.callback_query(F.data == "menu_saved_dishes")
async def show_saved_dishes_list(callback: types.CallbackQuery, state: FSMContext):
    """Show list of user's saved dishes."""
    await state.clear()
    user_id = callback.from_user.id
    
    async for session in get_db():
        stmt = (
            select(SavedDish)
            .where(SavedDish.user_id == user_id)
            .order_by(desc(SavedDish.created_at))
        )
        result = await session.execute(stmt)
        dishes = result.scalars().all()
    
    if not dishes:
        builder = InlineKeyboardBuilder()
        builder.button(text="🏗️ Создать блюдо", callback_data="menu_build_dish")
        builder.button(text="⬅️ Назад", callback_data="menu_i_ate")
        builder.adjust(1)
        
        photo_path = types.FSInputFile("assets/saved_dishes.png")
        caption = (
            "⭐ <b>Мои блюда</b>\n\n"
            "<i>У вас пока нет сохранённых блюд.</i>\n\n"
            "Создайте первое блюдо из того, что вы уже ели!"
        )
        
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
        return
    
    await render_dishes_list(callback.message, dishes, 0)
    await callback.answer()

async def render_dishes_list(message: types.Message, dishes: list, page: int):
    """Render paginated list of saved dishes with details in text."""
    ITEMS_PER_PAGE = 5
    total_pages = max(1, (len(dishes) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
    
    start_idx = page * ITEMS_PER_PAGE
    end_idx = min(start_idx + ITEMS_PER_PAGE, len(dishes))
    current_dishes = dishes[start_idx:end_idx]
    
    # Build text with numbered items and details
    text_lines = [f"⭐ <b>Ваши сохранённые блюда</b> ({len(dishes)}):\n"]
    
    for i, dish in enumerate(current_dishes, 1):
        # Format components
        comp_names = []
        if dish.components:
            for c in dish.components[:3]:
                comp_names.append(c.get("base_name", c.get("name", "?"))[:12])
        comp_str = ", ".join(comp_names)
        if len(dish.components) > 3:
            comp_str += f" +{len(dish.components)-3}"
        
        text_lines.append(
            f"<b>{i}. 🥪 {dish.name}</b> — {int(dish.total_calories)} ккал\n"
            f"    <i>{comp_str}</i>"
        )
    
    text_lines.append("\n<i>Нажмите кнопку, чтобы открыть.</i>")
    
    builder = InlineKeyboardBuilder()
    
    # Simple numbered buttons
    for i, dish in enumerate(current_dishes, 1):
        name_short = dish.name[:20] if len(dish.name) > 20 else dish.name
        builder.button(
            text=f"[{i}] {name_short}",
            callback_data=f"saved_dish_view:{dish.id}"
        )
    
    builder.adjust(1)
    
    # Navigation row
    nav_buttons = []
    if page > 0:
        nav_buttons.append(types.InlineKeyboardButton(text="⬅️", callback_data=f"dishes_page:{page-1}"))
    
    nav_buttons.append(types.InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="dishes_noop"))
    
    if page < total_pages - 1:
        nav_buttons.append(types.InlineKeyboardButton(text="➡️", callback_data=f"dishes_page:{page+1}"))
    
    if nav_buttons:
        builder.row(*nav_buttons)
    
    builder.row(
        types.InlineKeyboardButton(text="🏗️ Создать", callback_data="menu_build_dish"),
        types.InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_i_ate")
    )
    
    text = "\n".join(text_lines)

    
    try:
        await message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")

@router.callback_query(F.data.startswith("dishes_page:"))
async def dishes_pagination(callback: types.CallbackQuery, state: FSMContext):
    """Handle pagination for dishes list."""
    page = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    
    async for session in get_db():
        stmt = select(SavedDish).where(SavedDish.user_id == user_id).order_by(desc(SavedDish.created_at))
        result = await session.execute(stmt)
        dishes = result.scalars().all()
    
    await render_dishes_list(callback.message, dishes, page)
    await callback.answer()

@router.callback_query(F.data == "dishes_noop")
async def dishes_noop(callback: types.CallbackQuery):
    await callback.answer()

# =====================================================
# Dish Detail View
# =====================================================

@router.callback_query(F.data.startswith("saved_dish_view:"))
async def view_dish_detail(callback: types.CallbackQuery, state: FSMContext):
    """Show detail view of a saved dish."""
    dish_id = int(callback.data.split(":")[1])
    
    async for session in get_db():
        stmt = select(SavedDish).where(SavedDish.id == dish_id)
        result = await session.execute(stmt)
        dish = result.scalars().first()
    
    if not dish:
        await callback.answer("Блюдо не найдено!", show_alert=True)
        return
    
    # Format components list
    components_text = ""
    if dish.components:
        for comp in dish.components:
            comp_name = comp.get("name", comp.get("base_name", "?"))
            components_text += f"• {comp_name}\n"
    else:
        components_text = "<i>Нет данных о составе</i>"
    
    text = (
        f"🥪 <b>{dish.name}</b>\n\n"
        f"🔥 <b>{int(dish.total_calories)}</b> ккал\n"
        f"🥩 Белки: <b>{dish.total_protein:.1f}</b>г\n"
        f"🥑 Жиры: <b>{dish.total_fat:.1f}</b>г\n"
        f"🍞 Углеводы: <b>{dish.total_carbs:.1f}</b>г\n"
        f"🥬 Клетчатка: <b>{dish.total_fiber:.1f}</b>г\n\n"
        f"<b>Состав:</b>\n{components_text}"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Записать!", callback_data=f"saved_dish_log:{dish_id}")
    builder.button(text="🗑️ Удалить", callback_data=f"saved_dish_delete:{dish_id}")
    builder.button(text="⬅️ Назад", callback_data="menu_saved_dishes")
    builder.adjust(2, 1)
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()

# =====================================================
# Quick Log Dish
# =====================================================

@router.callback_query(F.data.startswith("saved_dish_log:"))
async def log_saved_dish(callback: types.CallbackQuery, state: FSMContext):
    """Log a saved dish to consumption."""
    dish_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    
    async for session in get_db():
        stmt = select(SavedDish).where(SavedDish.id == dish_id)
        result = await session.execute(stmt)
        dish = result.scalars().first()
        
        if not dish:
            await callback.answer("Блюдо не найдено!", show_alert=True)
            return
        
        # Create consumption log
        log = ConsumptionLog(
            user_id=user_id,
            product_name=dish.name,
            base_name=dish.name,
            calories=dish.total_calories,
            protein=dish.total_protein,
            fat=dish.total_fat,
            carbs=dish.total_carbs,
            fiber=dish.total_fiber,
            date=datetime.utcnow()
        )
        session.add(log)
        await session.commit()
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🍽️ Ещё", callback_data="menu_i_ate")
    builder.button(text="📊 Статистика", callback_data="menu_stats")
    builder.button(text="🏠 Меню", callback_data="main_menu")
    builder.adjust(1, 2)
    
    await callback.message.edit_text(
        f"✅ <b>Записано!</b>\n\n"
        f"🥪 <b>{dish.name}</b>\n\n"
        f"🔥 <b>{int(dish.total_calories)}</b> ккал\n"
        f"🥩 Белки: <b>{dish.total_protein:.1f}</b>г\n"
        f"🥑 Жиры: <b>{dish.total_fat:.1f}</b>г\n"
        f"🍞 Углеводы: <b>{dish.total_carbs:.1f}</b>г\n"
        f"🥬 Клетчатка: <b>{dish.total_fiber:.1f}</b>г",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer("✅ Записано!")

# =====================================================
# Delete Dish
# =====================================================

@router.callback_query(F.data.startswith("saved_dish_delete:"))
async def delete_saved_dish(callback: types.CallbackQuery, state: FSMContext):
    """Delete a saved dish."""
    dish_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    
    async for session in get_db():
        stmt = select(SavedDish).where(SavedDish.id == dish_id).where(SavedDish.user_id == user_id)
        result = await session.execute(stmt)
        dish = result.scalars().first()
        
        if not dish:
            await callback.answer("Блюдо не найдено!", show_alert=True)
            return
        
        dish_name = dish.name
        await session.delete(dish)
        await session.commit()
    
    await callback.answer(f"🗑️ \"{dish_name}\" удалено!")
    
    # Return to list
    async for session in get_db():
        stmt = select(SavedDish).where(SavedDish.user_id == user_id).order_by(desc(SavedDish.created_at))
        result = await session.execute(stmt)
        dishes = result.scalars().all()
    
    if dishes:
        await render_dishes_list(callback.message, dishes, 0)
    else:
        builder = InlineKeyboardBuilder()
        builder.button(text="🏗️ Создать блюдо", callback_data="menu_build_dish")
        builder.button(text="⬅️ Назад", callback_data="menu_i_ate")
        builder.adjust(1)
        
        await callback.message.edit_text(
            "⭐ <b>Мои блюда</b>\n\n"
            "<i>У вас больше нет сохранённых блюд.</i>",
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )

# =====================================================
# "Приёмы пищи" - Meal List View
# =====================================================

@router.callback_query(F.data == "menu_saved_meals")
async def show_saved_meals_list(callback: types.CallbackQuery, state: FSMContext):
    """Show list of user's saved meals."""
    await state.clear()
    user_id = callback.from_user.id
    
    async for session in get_db():
        stmt = (
            select(SavedDish)
            .where(SavedDish.user_id == user_id)
            .where(SavedDish.dish_type == "meal")
            .order_by(desc(SavedDish.created_at))
        )
        result = await session.execute(stmt)
        meals = result.scalars().all()
    
    if not meals:
        builder = InlineKeyboardBuilder()
        builder.button(text="🍳 Собрать приём пищи", callback_data="menu_build_meal")
        builder.button(text="⬅️ Назад", callback_data="menu_i_ate")
        builder.adjust(1)
        
        photo_path = types.FSInputFile("assets/saved_meals.png")
        caption = (
            "🍽️ <b>Приёмы пищи</b>\n\n"
            "<i>У вас пока нет сохранённых приёмов пищи.</i>\n\n"
            "Соберите первый из блюд и продуктов!"
        )
        
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
        return
    
    await render_meals_list(callback.message, meals, 0)
    await callback.answer()

async def render_meals_list(message: types.Message, meals: list, page: int):
    """Render paginated list of saved meals."""
    ITEMS_PER_PAGE = 6
    total_pages = max(1, (len(meals) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
    
    start_idx = page * ITEMS_PER_PAGE
    end_idx = min(start_idx + ITEMS_PER_PAGE, len(meals))
    current_meals = meals[start_idx:end_idx]
    
    # Build text with numbered items and details
    text_lines = [f"🍽️ <b>Ваши приёмы пищи</b> ({len(meals)}):\n"]
    
    for i, meal in enumerate(current_meals, 1):
        # Format components with icons
        comp_names = []
        if meal.components:
            for c in meal.components[:3]:
                is_dish = c.get("type") == "dish"
                icon = "⭐" if is_dish else ""
                name = c.get("base_name", c.get("name", "?"))
                # Only truncate products, keep full dish names
                if not is_dish and len(name) > 12:
                    name = name[:12]
                comp_names.append(icon + name)
        comp_str = ", ".join(comp_names)
        if len(meal.components) > 3:
            comp_str += f" +{len(meal.components)-3}"
        
        text_lines.append(
            f"<b>{i}. 🍽️ {meal.name}</b> — {int(meal.total_calories)} ккал\n"
            f"    <i>{comp_str}</i>"
        )
    
    text_lines.append("\n<i>Нажмите кнопку, чтобы открыть.</i>")
    
    builder = InlineKeyboardBuilder()
    
    # Simple numbered buttons
    for i, meal in enumerate(current_meals, 1):
        name_short = meal.name[:20] if len(meal.name) > 20 else meal.name
        builder.button(
            text=f"[{i}] {name_short}",
            callback_data=f"saved_meal_view:{meal.id}"
        )
    
    builder.adjust(1)
    
    # Navigation
    nav_buttons = []
    if page > 0:
        nav_buttons.append(types.InlineKeyboardButton(text="⬅️", callback_data=f"meals_page:{page-1}"))
    nav_buttons.append(types.InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="meals_noop"))
    if page < total_pages - 1:
        nav_buttons.append(types.InlineKeyboardButton(text="➡️", callback_data=f"meals_page:{page+1}"))
    if nav_buttons:
        builder.row(*nav_buttons)
    
    builder.row(
        types.InlineKeyboardButton(text="🍳 Собрать", callback_data="menu_build_meal"),
        types.InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_i_ate")
    )
    
    text = "\n".join(text_lines)
    
    try:
        await message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")

@router.callback_query(F.data.startswith("meals_page:"))
async def meals_pagination(callback: types.CallbackQuery, state: FSMContext):
    page = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    
    async for session in get_db():
        stmt = select(SavedDish).where(SavedDish.user_id == user_id).where(SavedDish.dish_type == "meal").order_by(desc(SavedDish.created_at))
        result = await session.execute(stmt)
        meals = result.scalars().all()
    
    await render_meals_list(callback.message, meals, page)
    await callback.answer()

@router.callback_query(F.data == "meals_noop")
async def meals_noop(callback: types.CallbackQuery):
    await callback.answer()

# Meal detail view reuses dish view logic
@router.callback_query(F.data.startswith("saved_meal_view:"))
async def view_meal_detail(callback: types.CallbackQuery, state: FSMContext):
    meal_id = int(callback.data.split(":")[1])
    
    async for session in get_db():
        stmt = select(SavedDish).where(SavedDish.id == meal_id)
        result = await session.execute(stmt)
        meal = result.scalars().first()
    
    if not meal:
        await callback.answer("Приём пищи не найден!", show_alert=True)
        return
    
    components_text = ""
    if meal.components:
        for comp in meal.components:
            comp_name = comp.get("name", comp.get("base_name", "?"))
            comp_type = comp.get("type", "product")
            icon = "⭐" if comp_type == "dish" else "📋"
            components_text += f"{icon} {comp_name}\n"
    else:
        components_text = "<i>Нет данных</i>"
    
    text = (
        f"🍽️ <b>{meal.name}</b>\n\n"
        f"🔥 <b>{int(meal.total_calories)}</b> ккал\n"
        f"🥩 Белки: <b>{meal.total_protein:.1f}</b>г\n"
        f"🥑 Жиры: <b>{meal.total_fat:.1f}</b>г\n"
        f"🍞 Углеводы: <b>{meal.total_carbs:.1f}</b>г\n"
        f"🥬 Клетчатка: <b>{meal.total_fiber:.1f}</b>г\n\n"
        f"<b>Состав:</b>\n{components_text}"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Записать!", callback_data=f"saved_meal_log:{meal_id}")
    builder.button(text="🗑️ Удалить", callback_data=f"saved_meal_delete:{meal_id}")
    builder.button(text="⬅️ Назад", callback_data="menu_saved_meals")
    builder.adjust(2, 1)
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("saved_meal_log:"))
async def log_saved_meal(callback: types.CallbackQuery, state: FSMContext):
    meal_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    
    async for session in get_db():
        stmt = select(SavedDish).where(SavedDish.id == meal_id)
        result = await session.execute(stmt)
        meal = result.scalars().first()
        
        if not meal:
            await callback.answer("Не найдено!", show_alert=True)
            return
        
        log = ConsumptionLog(
            user_id=user_id,
            product_name=meal.name,
            base_name=meal.name,
            calories=meal.total_calories,
            protein=meal.total_protein,
            fat=meal.total_fat,
            carbs=meal.total_carbs,
            fiber=meal.total_fiber,
            date=datetime.utcnow()
        )
        session.add(log)
        await session.commit()
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🍽️ Ещё", callback_data="menu_i_ate")
    builder.button(text="📊 Статистика", callback_data="menu_stats")
    builder.button(text="🏠 Меню", callback_data="main_menu")
    builder.adjust(1, 2)
    
    await callback.message.edit_text(
        f"✅ <b>Записано!</b>\n\n"
        f"🍽️ <b>{meal.name}</b>\n\n"
        f"🔥 <b>{int(meal.total_calories)}</b> ккал\n"
        f"🥩 Белки: <b>{meal.total_protein:.1f}</b>г\n"
        f"🥑 Жиры: <b>{meal.total_fat:.1f}</b>г\n"
        f"🍞 Углеводы: <b>{meal.total_carbs:.1f}</b>г\n"
        f"🥬 Клетчатка: <b>{meal.total_fiber:.1f}</b>г",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer("✅ Записано!")

@router.callback_query(F.data.startswith("saved_meal_delete:"))
async def delete_saved_meal(callback: types.CallbackQuery, state: FSMContext):
    meal_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    
    async for session in get_db():
        stmt = select(SavedDish).where(SavedDish.id == meal_id).where(SavedDish.user_id == user_id)
        result = await session.execute(stmt)
        meal = result.scalars().first()
        
        if not meal:
            await callback.answer("Не найдено!", show_alert=True)
            return
        
        meal_name = meal.name
        await session.delete(meal)
        await session.commit()
    
    await callback.answer(f"🗑️ \"{meal_name}\" удалено!")
    
    async for session in get_db():
        stmt = select(SavedDish).where(SavedDish.user_id == user_id).where(SavedDish.dish_type == "meal").order_by(desc(SavedDish.created_at))
        result = await session.execute(stmt)
        meals = result.scalars().all()
    
    if meals:
        await render_meals_list(callback.message, meals, 0)
    else:
        builder = InlineKeyboardBuilder()
        builder.button(text="🍳 Собрать приём пищи", callback_data="menu_build_meal")
        builder.button(text="⬅️ Назад", callback_data="menu_i_ate")
        builder.adjust(1)
        
        await callback.message.edit_text(
            "🍽️ <b>Приёмы пищи</b>\n\n<i>У вас больше нет сохранённых приёмов.</i>",
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )

# =====================================================
# Build Meal - Mixed Selection (Dishes + Products)
# =====================================================

@router.callback_query(F.data == "menu_build_meal")
async def start_build_meal(callback: types.CallbackQuery, state: FSMContext):
    """Start building a meal from dishes + products."""
    await state.clear()
    user_id = callback.from_user.id
    
    items = []  # List of {"type": "dish"|"product", "id": ..., "name": ..., "calories": ...}
    
    async for session in get_db():
        # 1. Fetch saved dishes
        stmt = select(SavedDish).where(SavedDish.user_id == user_id).where(SavedDish.dish_type == "dish").order_by(desc(SavedDish.created_at))
        result = await session.execute(stmt)
        dishes = result.scalars().all()
        
        for d in dishes:
            items.append({
                "type": "dish",
                "id": d.id,
                "name": d.name,
                "calories": d.total_calories,
                "protein": d.total_protein,
                "fat": d.total_fat,
                "carbs": d.total_carbs,
                "fiber": d.total_fiber
            })
        
        # 2. Fetch unique products from history
        stmt = (
            select(ConsumptionLog)
            .where(ConsumptionLog.user_id == user_id)
            .where(ConsumptionLog.base_name != None)
            .order_by(desc(ConsumptionLog.date))
            .limit(500)
        )
        result = await session.execute(stmt)
        logs = result.scalars().all()
    
    # Group by base_name, take most recent
    seen = set()
    for log in logs:
        if log.base_name not in seen:
            seen.add(log.base_name)
            items.append({
                "type": "product",
                "id": log.id,
                "name": log.base_name,
                "full_name": log.product_name,
                "calories": log.calories,
                "protein": log.protein,
                "fat": log.fat,
                "carbs": log.carbs,
                "fiber": log.fiber
            })
    
    if not items:
        await callback.answer("Нет блюд или продуктов! Сначала что-нибудь съешьте.", show_alert=True)
        return
    
    await state.set_state(SavedDishStates.building_meal)
    await state.update_data(
        meal_items=items,
        selected_indices=[],
        current_page=0
    )
    
    await render_meal_builder_ui(callback.message, state)
    await callback.answer()

async def render_meal_builder_ui(message: types.Message, state: FSMContext):
    data = await state.get_data()
    items = data.get("meal_items", [])
    selected_indices = set(data.get("selected_indices", []))
    page = data.get("current_page", 0)
    
    ITEMS_PER_PAGE = 8
    total_pages = max(1, (len(items) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
    
    start_idx = page * ITEMS_PER_PAGE
    end_idx = min(start_idx + ITEMS_PER_PAGE, len(items))
    current_batch = items[start_idx:end_idx]
    
    builder = InlineKeyboardBuilder()
    
    for i, item in enumerate(current_batch):
        real_idx = start_idx + i
        is_selected = real_idx in selected_indices
        mark = "✅" if is_selected else "⬜"
        icon = "⭐" if item["type"] == "dish" else "📋"
        builder.button(
            text=f"{mark} {icon} {item['name']}", 
            callback_data=f"meal_toggle:{real_idx}"
        )
    
    builder.adjust(1)
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(types.InlineKeyboardButton(text="⬅️", callback_data="meal_prev"))
        
    count = len(selected_indices)
    action_text = f"💾 Сохранить ({count})" if count > 0 else "Выберите..."
    callback_action = "meal_ask_name" if count > 0 else "meal_noop"
    nav_buttons.append(types.InlineKeyboardButton(text=action_text, callback_data=callback_action))
    
    if page < total_pages - 1:
        nav_buttons.append(types.InlineKeyboardButton(text="➡️", callback_data="meal_next"))
        
    builder.row(*nav_buttons)
    builder.row(types.InlineKeyboardButton(text="❌ Отмена", callback_data="menu_i_ate"))
    
    text = (
        "🍳 <b>Конструктор приёма пищи</b>\n\n"
        "Выберите блюда (⭐) и/или продукты (📋):\n"
        f"<i>Страница {page+1}/{total_pages}</i>"
    )
    
    try:
        await message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")

@router.callback_query(SavedDishStates.building_meal, F.data.startswith("meal_toggle:"))
async def on_meal_toggle(callback: types.CallbackQuery, state: FSMContext):
    idx = int(callback.data.split(":")[1])
    data = await state.get_data()
    selected = set(data.get("selected_indices", []))
    
    if idx in selected:
        selected.remove(idx)
    else:
        selected.add(idx)
        
    await state.update_data(selected_indices=list(selected))
    await render_meal_builder_ui(callback.message, state)
    await callback.answer()

@router.callback_query(SavedDishStates.building_meal, F.data == "meal_prev")
async def on_meal_prev(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    p = data.get("current_page", 0)
    if p > 0:
        await state.update_data(current_page=p-1)
        await render_meal_builder_ui(callback.message, state)
    await callback.answer()

@router.callback_query(SavedDishStates.building_meal, F.data == "meal_next")
async def on_meal_next(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.update_data(current_page=data.get("current_page", 0)+1)
    await render_meal_builder_ui(callback.message, state)
    await callback.answer()

@router.callback_query(SavedDishStates.building_meal, F.data == "meal_noop")
async def meal_noop(callback: types.CallbackQuery):
    await callback.answer("Выберите хотя бы один элемент!")

@router.callback_query(SavedDishStates.building_meal, F.data == "meal_ask_name")
async def ask_meal_name(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(SavedDishStates.naming_meal)
    await callback.message.edit_text(
        "📝 <b>Как назовём приём пищи?</b>\n\n"
        "Пришлите название (например: <i>Завтрак</i>, <i>Обед</i>, <i>Перекус</i>).",
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(SavedDishStates.naming_meal, F.text)
async def save_meal_final(message: types.Message, state: FSMContext):
    name = message.text.strip()
    data = await state.get_data()
    items = data["meal_items"]
    selected_indices = data["selected_indices"]
    user_id = message.from_user.id
    
    status_msg = await message.answer(f"💾 Сохраняю <b>{name}</b>...", parse_mode="HTML")
    
    components = []
    total_cal = 0.0
    total_prot = 0.0
    total_fat = 0.0
    total_carb = 0.0
    total_fib = 0.0
    
    for idx in selected_indices:
        item = items[idx]
        components.append({
            "type": item["type"],
            "name": item.get("full_name", item["name"]),
            "base_name": item["name"],
            "calories": item.get("calories", 0),
            "protein": item.get("protein", 0),
            "fat": item.get("fat", 0),
            "carbs": item.get("carbs", 0),
            "fiber": item.get("fiber", 0)
        })
        total_cal += item.get("calories", 0) or 0
        total_prot += item.get("protein", 0) or 0
        total_fat += item.get("fat", 0) or 0
        total_carb += item.get("carbs", 0) or 0
        total_fib += item.get("fiber", 0) or 0
    
    async for session in get_db():
        new_meal = SavedDish(
            user_id=user_id,
            name=name,
            dish_type="meal",
            components=components,
            total_calories=total_cal,
            total_protein=total_prot,
            total_fat=total_fat,
            total_carbs=total_carb,
            total_fiber=total_fib
        )
        session.add(new_meal)
        await session.commit()
        
    await state.clear()
    
    # Format components list
    comp_lines = []
    for c in components:
        icon = "⭐" if c.get("type") == "dish" else "📋"
        comp_lines.append(f"{icon} {c.get('name', c.get('base_name', '?'))}")
    comp_text = "\n".join(comp_lines)
    
    await status_msg.edit_text(
        f"✅ <b>Приём пищи сохранён!</b>\n\n"
        f"🍽️ <b>{name}</b>\n\n"
        f"🔥 <b>{int(total_cal)}</b> ккал\n"
        f"🥩 Белки: <b>{total_prot:.1f}</b>г\n"
        f"🥑 Жиры: <b>{total_fat:.1f}</b>г\n"
        f"🍞 Углеводы: <b>{total_carb:.1f}</b>г\n"
        f"🥬 Клетчатка: <b>{total_fib:.1f}</b>г\n\n"
        f"<b>Состав:</b>\n{comp_text}\n\n"
        f"Теперь используйте <i>\"🍽️ Приёмы пищи\"</i>!",
        parse_mode="HTML"
    )

