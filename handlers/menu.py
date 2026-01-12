"""Module for main menu handlers.

Contains:
- show_main_menu: Display main menu with all available features
- back_to_main: Return to main menu from any screen
- menu_check_handler: Show receipt upload instructions
- menu_help_handler: Show help information
- menu_settings_handler: Show settings menu
"""
from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router()



@router.message(F.text.in_({"🏠 Главное меню", "Меню", "Главное меню", "menu", "Menu"}))
async def menu_button_handler(message: types.Message) -> None:
    """Handle persistent 'Main Menu' button click."""
    await show_main_menu(message, message.from_user.first_name)


@router.callback_query(F.data == "main_menu")
async def back_to_main(callback: types.CallbackQuery) -> None:
    """Return to the main menu by editing the current message.

    Args:
        callback: Telegram callback query

    Returns:
        None

    """
    await show_main_menu(callback.message, callback.from_user.first_name)
    await callback.answer()


async def show_main_menu(message: types.Message, user_name: str) -> None:
    """Display the main menu with inline buttons.

    Shows all available bot features: shopping mode, receipt upload,
    fridge, recipes, stats, shopping list, settings, and help.

    Args:
        message: Telegram message object to edit or send menu to
        user_name: User's first name for personalization

    Returns:
        None

    """
    builder = InlineKeyboardBuilder()

    # Row 0: BIG "I ATE" button - top priority
    builder.button(text="🍽️ Я ПОЕЛ!", callback_data="menu_i_ate")
    
    # TODO [CURATOR-2.1]: Add curator dashboard button here (visible only if user.role == "curator")
    # builder.button(text="👨‍🏫 Кабинет Куратора", callback_data="curator_dashboard")
    
    # Row 1: Fridge
    builder.button(text="🧊 Холодильник", callback_data="menu_fridge")

    # Row 2: Core
    builder.button(text="📸 Загрузить чек", callback_data="menu_check")
    builder.button(text="👨‍🍳 Рецепты", callback_data="menu_recipes")

    # Row 3: Stats
    builder.button(text="📊 Статистика", callback_data="menu_stats")
    builder.button(text="⚖️ Вес", callback_data="menu_weight")

    # Row 4: System
    builder.button(text="⚙️ Настройки", callback_data="menu_settings")
    builder.button(text="ℹ️ Справка", callback_data="menu_help")
    
    # Row 5: Contact
    builder.button(text="📩 Написать разработчику", callback_data="menu_contact_dev")

    # Row 6: Admin
    from config import settings
    if message.from_user.id in settings.ADMIN_IDS:
        builder.button(text="🔄 RESTART BOT", callback_data="admin_restart_bot")
        builder.button(text="📨 НАПИСАТЬ ЮЗЕРУ", callback_data="admin_send_message")

    # Layout: 1 (I ATE), 1 (fridge), 2, 2, 2, 1, (2 for admin)
    rows = [1, 1, 2, 2, 2, 1]
    if message.from_user.id in settings.ADMIN_IDS:
        rows.append(2)
        
    builder.adjust(*rows)


    # Image path
    photo_path = types.FSInputFile("assets/main_menu.png")

    caption = (
        f"🍽️ <b>FoodFlow</b>\n\n"
        f"Привет, {user_name}! 👋\n"
        "Я помогу тебе следить за питанием и продуктами.\n\n"
        "<b>Что будем делать?</b>"
    )

    # Try to edit if possible (if previous was photo), otherwise send new
    try:
        await message.edit_media(
            media=types.InputMediaPhoto(media=photo_path, caption=caption, parse_mode="HTML"),
            reply_markup=builder.as_markup()
        )
    except Exception:
        # If edit fails (e.g. previous was text), delete and send new photo
        try:
             await message.delete()
        except Exception:
            pass
        await message.answer_photo(
            photo=photo_path,
            caption=caption,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )

@router.callback_query(F.data == "menu_check")
async def menu_check_handler(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Show receipt upload instructions.

    Displays information about how to upload receipts
    and what the bot can recognize. Set state to waiting for receipt.

    Args:
        callback: Telegram callback query
        state: FSM Context

    Returns:
        None

    """
    from handlers.shopping import ShoppingMode
    
    await state.set_state(ShoppingMode.waiting_for_receipt)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="main_menu")

    photo_path = types.FSInputFile("assets/check_upload.png")
    caption = (
        "📸 <b>Загрузка чека</b>\n\n"
        "Просто отправь мне фото чека, и я добавлю продукты в холодильник.\n"
        "Я умею распознавать товары, цены и вес."
    )

    try:
        await callback.message.edit_media(
            media=types.InputMediaPhoto(media=photo_path, caption=caption, parse_mode="HTML"),
            reply_markup=builder.as_markup()
        )
    except Exception:
        await callback.message.delete()
        await callback.message.answer_photo(
            photo=photo_path,
            caption=caption,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    await callback.answer()



@router.callback_query(F.data == "menu_help")
async def menu_help_handler(callback: types.CallbackQuery) -> None:
    """Show help information.

    Displays instructions on how to use the bot's main features:
    receipt upload, fridge management, recipes, and shopping.

    Args:
        callback: Telegram callback query

    Returns:
        None

    """
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="main_menu")

    photo_path = types.FSInputFile("assets/help.png")
    caption = (
        "ℹ️ <b>Справка</b>\n\n"
        "<b>Как это работает?</b>\n"
        "1. 📸 <b>Чек:</b> Сфоткай чек после магазина.\n"
        "2. 🧊 <b>Холодильник:</b> Я сохраню все продукты.\n"
        "3. 👨‍🍳 <b>Рецепты:</b> Предложу, что приготовить из того, что есть.\n"
        "4. 🛒 <b>Магазин:</b> Помогу сравнить цены и найти товары."
    )

    try:
        await callback.message.edit_media(
            media=types.InputMediaPhoto(media=photo_path, caption=caption, parse_mode="HTML"),
            reply_markup=builder.as_markup()
        )
    except Exception:
        await callback.message.delete()
        await callback.message.answer_photo(
            photo=photo_path,
            caption=caption,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    await callback.answer()


