from aiogram import Router, F, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import Command

router = Router()

@router.callback_query(F.data == "main_menu")
async def back_to_main(callback: types.CallbackQuery):
    """Returns to the main menu by editing the current message."""
    await show_main_menu(callback.message, callback.from_user.first_name)
    await callback.answer()

async def show_main_menu(message: types.Message, user_name: str):
    """Displays the main menu with inline buttons."""
    builder = InlineKeyboardBuilder()
    
    # Row 1: Shopping Mode (Prominent)
    builder.button(text="🛒 Иду в магазин", callback_data="start_shopping_mode")
    
    # Row 2: Core Features
    builder.button(text="📸 Загрузить чек", callback_data="menu_check")
    builder.button(text="🧊 Холодильник", callback_data="menu_fridge")
    
    # Row 3: AI Features
    builder.button(text="👨‍🍳 Рецепты", callback_data="menu_recipes")
    builder.button(text="📊 Статистика", callback_data="menu_stats")
    
    # Row 4: System
    builder.button(text="⚙️ Настройки", callback_data="menu_settings")
    builder.button(text="ℹ️ Справка", callback_data="menu_help")
    
    builder.adjust(1, 2, 2, 2)
    
    text = (
        f"🍽️ <b>FoodFlow</b>\n\n"
        f"Привет, {user_name}! 👋\n"
        "Я помогу тебе следить за питанием и продуктами.\n\n"
        "<b>Что будем делать?</b>"
    )
    
    # Try to edit if possible, otherwise send new
    try:
        await message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")

@router.callback_query(F.data == "menu_check")
async def menu_check_handler(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="main_menu")
    
    await callback.message.edit_text(
        "📸 <b>Загрузка чека</b>\n\n"
        "Просто отправь мне фото чека, и я добавлю продукты в холодильник.\n"
        "Я умею распознавать товары, цены и вес.",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "menu_settings")
async def menu_settings_handler(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="main_menu")
    
    await callback.message.edit_text(
        "⚙️ <b>Настройки</b>\n\n"
        "Тут пока пусто, но скоро можно будет настроить цели по КБЖУ и предпочтения.",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "menu_help")
async def menu_help_handler(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="main_menu")
    
    await callback.message.edit_text(
        "ℹ️ <b>Справка</b>\n\n"
        "<b>Как это работает?</b>\n"
        "1. 📸 <b>Чек:</b> Сфоткай чек после магазина.\n"
        "2. 🧊 <b>Холодильник:</b> Я сохраню все продукты.\n"
        "3. 👨‍🍳 <b>Рецепты:</b> Предложу, что приготовить из того, что есть.\n"
        "4. 🛒 <b>Магазин:</b> Помогу сравнить цены и найти товары.",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()
