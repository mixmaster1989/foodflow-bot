from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from database.base import get_db
from database.models import UserSettings

router = Router()

class SettingsStates(StatesGroup):
    waiting_for_calories = State()
    waiting_for_protein = State()
    waiting_for_fat = State()
    waiting_for_carbs = State()
    waiting_for_allergies = State()

@router.callback_query(F.data == "menu_settings")
async def show_settings(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    async for session in get_db():
        stmt = select(UserSettings).where(UserSettings.user_id == user_id)
        settings = (await session.execute(stmt)).scalar_one_or_none()
        
        if not settings:
            # Create default settings
            settings = UserSettings(user_id=user_id)
            session.add(settings)
            await session.commit()
            await session.refresh(settings)
        
        text = (
            "⚙️ <b>Настройки профиля</b>\n\n"
            "🎯 <b>Цели КБЖУ:</b>\n"
            f"🔥 Калории: <b>{settings.calorie_goal}</b> ккал\n"
            f"🥩 Белки: <b>{settings.protein_goal}</b> г\n"
            f"🥑 Жиры: <b>{settings.fat_goal}</b> г\n"
            f"🍞 Углеводы: <b>{settings.carb_goal}</b> г\n\n"
            f"🚫 <b>Аллергии/Исключения:</b>\n"
            f"{settings.allergies or 'Нет'}"
        )
        
        builder = InlineKeyboardBuilder()
        builder.button(text="🎯 Изменить цели КБЖУ", callback_data="settings_edit_goals")
        builder.button(text="🚫 Изменить аллергии", callback_data="settings_edit_allergies")
        builder.button(text="🔙 Назад", callback_data="main_menu")
        builder.adjust(1)
        
        # Image path
        photo_path = types.FSInputFile("FoodFlow/assets/main_menu.png")
        
        # Try to edit media (photo), if fails try edit_text, if fails delete and send new
        try:
            await callback.message.edit_media(
                media=types.InputMediaPhoto(media=photo_path, caption=text, parse_mode="HTML"),
                reply_markup=builder.as_markup()
            )
        except Exception:
            try:
                await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
            except Exception:
                await callback.message.delete()
                await callback.message.answer_photo(
                    photo=photo_path,
                    caption=text,
                    reply_markup=builder.as_markup(),
                    parse_mode="HTML"
                )
        await callback.answer()

@router.callback_query(F.data == "settings_edit_goals")
async def start_edit_goals(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(SettingsStates.waiting_for_calories)
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Отмена", callback_data="menu_settings")
    
    edit_text = (
        "🎯 <b>Настройка целей</b>\n\n"
        "Введите вашу дневную норму <b>калорий</b> (числом, например 2000):"
    )
    
    try:
        await callback.message.edit_text(edit_text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        await callback.message.delete()
        await callback.message.answer(edit_text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()

@router.message(SettingsStates.waiting_for_calories)
async def set_calories(message: types.Message, state: FSMContext):
    try:
        calories = int(message.text)
        await state.update_data(calorie_goal=calories)
        await state.set_state(SettingsStates.waiting_for_protein)
        await message.answer("Отлично! Теперь введите норму <b>белков</b> (г):", parse_mode="HTML")
    except ValueError:
        await message.answer("Пожалуйста, введите целое число.")

@router.message(SettingsStates.waiting_for_protein)
async def set_protein(message: types.Message, state: FSMContext):
    try:
        protein = int(message.text)
        await state.update_data(protein_goal=protein)
        await state.set_state(SettingsStates.waiting_for_fat)
        await message.answer("Теперь введите норму <b>жиров</b> (г):", parse_mode="HTML")
    except ValueError:
        await message.answer("Пожалуйста, введите целое число.")

@router.message(SettingsStates.waiting_for_fat)
async def set_fat(message: types.Message, state: FSMContext):
    try:
        fat = int(message.text)
        await state.update_data(fat_goal=fat)
        await state.set_state(SettingsStates.waiting_for_carbs)
        await message.answer("И наконец, норму <b>углеводов</b> (г):", parse_mode="HTML")
    except ValueError:
        await message.answer("Пожалуйста, введите целое число.")

@router.message(SettingsStates.waiting_for_carbs)
async def set_carbs(message: types.Message, state: FSMContext):
    try:
        carbs = int(message.text)
        data = await state.get_data()
        
        async for session in get_db():
            stmt = select(UserSettings).where(UserSettings.user_id == message.from_user.id)
            settings = (await session.execute(stmt)).scalar_one_or_none()
            
            if settings:
                settings.calorie_goal = data['calorie_goal']
                settings.protein_goal = data['protein_goal']
                settings.fat_goal = data['fat_goal']
                settings.carb_goal = carbs
                await session.commit()
        
        await state.clear()
        
        # Show updated settings
        # We can't easily call callback handler from message handler without mocking, 
        # so let's just send a message with button to go back
        builder = InlineKeyboardBuilder()
        builder.button(text="🔙 Вернуться в настройки", callback_data="menu_settings")
        
        await message.answer("✅ Цели успешно обновлены!", reply_markup=builder.as_markup())
        
    except ValueError:
        await message.answer("Пожалуйста, введите целое число.")

@router.callback_query(F.data == "settings_edit_allergies")
async def start_edit_allergies(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(SettingsStates.waiting_for_allergies)
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Отмена", callback_data="menu_settings")
    
    edit_text = (
        "🚫 <b>Настройка аллергий</b>\n\n"
        "Напишите продукты, которые нужно исключить (через запятую).\n"
        "Например: <i>орехи, молоко, мед</i>\n"
        "Или напишите 'нет', чтобы очистить."
    )
    
    try:
        await callback.message.edit_text(edit_text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        await callback.message.delete()
        await callback.message.answer(edit_text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()

@router.message(SettingsStates.waiting_for_allergies)
async def set_allergies(message: types.Message, state: FSMContext):
    allergies = message.text
    if allergies.lower() in ['нет', 'no', '-', 'none']:
        allergies = None
        
    async for session in get_db():
        stmt = select(UserSettings).where(UserSettings.user_id == message.from_user.id)
        settings = (await session.execute(stmt)).scalar_one_or_none()
        
        if settings:
            settings.allergies = allergies
            await session.commit()
            
    await state.clear()
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Вернуться в настройки", callback_data="menu_settings")
    
    await message.answer("✅ Список исключений обновлен!", reply_markup=builder.as_markup())
