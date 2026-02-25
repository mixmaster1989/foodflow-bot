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
from aiogram.filters import Command
from aiogram.types import Message

router = Router()


@router.message(Command("start"))
async def command_start_handler(message: Message, user_tier: str = "free") -> None:
    """Handle /start command.

    Args:
        message: Telegram message object
    """
    await show_main_menu(message, message.from_user.first_name, message.from_user.id, user_tier)


@router.message(F.text.in_({"🏠 Главное меню", "Меню", "Главное меню", "menu", "Menu"}))
async def menu_button_handler(message: types.Message, state: FSMContext, user_tier: str = "free") -> None:
    """Handle persistent 'Main Menu' button click."""
    await state.clear()  # Clear any active state!
    await show_main_menu(message, message.from_user.first_name, message.from_user.id, user_tier)


@router.callback_query(F.data == "main_menu")
async def main_menu_callback_handler(callback: types.CallbackQuery, state: FSMContext, user_tier: str = "free") -> None:
    """Handle 'main_menu' callback to return to the dashboard."""
    await state.clear()  # Clear any active state!
    await show_main_menu(callback.message, callback.from_user.first_name, callback.from_user.id, user_tier)
    await callback.answer()


async def show_main_menu(message: types.Message, user_name: str, user_id: int, user_tier: str = "free") -> None:
    """Display the main menu with inline buttons.

    Shows all available bot features: shopping mode, receipt upload,
    fridge, recipes, stats, shopping list, settings, and help.

    Args:
        message: Telegram message object to edit or send menu to
        user_name: User's first name for personalization
        user_id: Telegram user ID for DB lookup

    Returns:
        None

    """
    builder = InlineKeyboardBuilder()

    # Check user role and gender from DB
    is_curator = False
    is_female = False
    from database.base import get_db
    from database.models import User, UserSettings, ConsumptionLog, WaterLog
    from sqlalchemy import select, and_, func
    from datetime import datetime, date
    async for session in get_db():
        stmt = select(User).where(User.id == user_id)
        user = (await session.execute(stmt)).scalar_one_or_none()
        if user and user.role == "curator":
            is_curator = True
        
        # Check gender from settings
        settings_stmt = select(UserSettings).where(UserSettings.user_id == user_id)
        settings = (await session.execute(settings_stmt)).scalar_one_or_none()
        if settings and settings.gender == "female":
            is_female = True
    
        # Get daily metrics (calories, macros) for display
        today = date.today()
        metrics_stmt = select(
            func.sum(ConsumptionLog.calories),
            func.sum(ConsumptionLog.protein),
            func.sum(ConsumptionLog.fat),
            func.sum(ConsumptionLog.carbs),
            func.sum(ConsumptionLog.fiber)
        ).where(
            and_(
                ConsumptionLog.user_id == user_id,
                func.date(ConsumptionLog.date) == today
            )
        )
        row = (await session.execute(metrics_stmt)).fetchone()
        
        total_metrics = {
            "calories": row[0] or 0,
            "protein": row[1] or 0,
            "fat": row[2] or 0,
            "carbs": row[3] or 0,
            "fiber": row[4] or 0
        }
        
        # Get daily water
        water_stmt = select(func.sum(WaterLog.amount_ml)).where(
            and_(
                WaterLog.user_id == user_id,
                func.date(WaterLog.date) == today
            )
        )
        water_total = (await session.execute(water_stmt)).scalar() or 0
        
        goals = {
            "calories": settings.calorie_goal if settings else 2000,
            "water": settings.water_goal if settings else 2000
        }
        
    # Row 0: BIG "I ATE" button - gender aware
    ate_text = "🍽️ Я СЪЕЛА!" if is_female else "🍽️ Я СЪЕЛ!"
    builder.button(text=ate_text, callback_data="menu_i_ate")
    builder.button(text="💧 Вода", callback_data="menu_water")
    
    # Curator dashboard button (visible only for curators)
    if is_curator:
        builder.button(text="👨‍🏫 Кабинет Куратора", callback_data="curator_dashboard")
    
    # Row 1: Fridge
    builder.button(text="🧊 Холодильник", callback_data="menu_fridge")

    # Row 2: Core
    builder.button(text="👨‍🍳 Рецепты", callback_data="menu_recipes")

    # Row 3: Stats
    builder.button(text="📊 Статистика", callback_data="menu_stats")
    builder.button(text="⚖️ Вес", callback_data="menu_weight")

    # Row 4: System
    builder.button(text="⚙️ Настройки", callback_data="menu_settings")
    builder.button(text="ℹ️ Справка", callback_data="menu_help")
    
    # Row 5: Web App
    if user_tier != "free":
        from aiogram.types import WebAppInfo
        builder.button(text="📱 FoodFlow App", web_app=WebAppInfo(url="https://tretyakov-igor.tech/foodflow/"))

    # Row 6: Contact
    builder.button(text="📩 Написать разработчику", callback_data="menu_contact_dev")

    # Row 6: Admin
    from config import settings
    if message.from_user.id in settings.ADMIN_IDS:
        builder.button(text="🔄 RESTART BOT", callback_data="admin_restart_bot")
        builder.button(text="📨 НАПИСАТЬ ЮЗЕРУ", callback_data="admin_send_message")

    # Layout depends on curator status
    if is_curator:
        rows = [2, 1, 1, 1, 2, 2, 1, 1]  # I ATE/Water, Curator, Fridge, Recipes(1), Stats(2), System(2), WebApp(1), Contact(1)
    else:
        rows = [2, 1, 1, 2, 2, 1, 1]  # I ATE/Water, Fridge, Recipes(1), Stats(2), System(2), WebApp(1), Contact(1)
    if message.from_user.id in settings.ADMIN_IDS:
        rows.append(2)
        
    builder.adjust(*rows)

    # Get recent logs for the card
    logs = []
    async for session in get_db():
        stmt = select(ConsumptionLog).where(
            and_(
                ConsumptionLog.user_id == user_id,
                func.date(ConsumptionLog.date) == today
            )
        ).order_by(ConsumptionLog.date.desc()).limit(10)
        logs = (await session.execute(stmt)).scalars().all()
        
    # Generate the dynamic dashboard card
    from services.image_renderer import draw_daily_card
    photo_bytes = draw_daily_card(user_name, today, logs, total_metrics, goals, water_total)
    
    # Use InputMediaPhoto instead of Animation
    media_file = types.BufferedInputFile(photo_bytes.getvalue(), filename="dashboard.png")

    caption = (
        f"🍽️ <b>FoodFlow</b>\n\n"
        f"Привет, <b>{user_name}</b>! 👋\n\n"
        f"📊 <b>Показатели сегодня:</b>\n"
        f"🔥 <code>{total_metrics['calories']:.0f} / {goals['calories']} ккал</code>\n"
        f"💧 <code>{water_total} / {goals['water']} мл</code>\n"
        f"🥦 БЖУ: <code>{total_metrics['protein']:.0f}|{total_metrics['fat']:.0f}|{total_metrics['carbs']:.0f}</code> 🥬 <code>{total_metrics['fiber']:.0f}г</code>\n\n"
        "<b>Что будем делать?</b>"
    )

    # Try to edit if possible, otherwise send new photo
    try:
        await message.edit_media(
            media=types.InputMediaPhoto(media=media_file, caption=caption, parse_mode="HTML"),
            reply_markup=builder.as_markup()
        )
    except Exception:
        # If edit fails, delete and send new photo
        try:
             await message.delete()
        except Exception:
            pass
        await message.answer_photo(
            photo=media_file,
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


