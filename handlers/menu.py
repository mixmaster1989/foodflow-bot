"""Module for main menu handlers.

Contains:
- show_main_menu: Display main menu with all available features
- back_to_main: Return to main menu from any screen
- menu_check_handler: Show receipt upload instructions
- menu_help_handler: Show help information
- menu_settings_handler: Show settings menu
"""
from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router()




@router.message(F.text.in_({"🏠 Главное меню", "Меню", "Главное меню", "menu", "Menu"}))
async def menu_button_handler(message: types.Message, state: FSMContext, user_tier: str = "free") -> None:
    """Handle persistent 'Main Menu' button click."""
    await state.clear()  # Clear any active state!
    await show_main_menu(message, message.from_user.first_name, message.from_user.id, user_tier)


@router.callback_query(F.data == "main_menu")
async def main_menu_callback_handler(callback: types.CallbackQuery, state: FSMContext, user_tier: str = "free") -> None:
    """Handle 'main_menu' callback to return to the dashboard."""
    await callback.answer()
    await state.clear()  # Clear any active state!
    await show_main_menu(callback.message, callback.from_user.first_name, callback.from_user.id, user_tier)


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
    from datetime import date

    from sqlalchemy import and_, func, select

    from database.base import get_db
    from database.models import ConsumptionLog, User, UserSettings, WaterLog, Subscription
    
    today = date.today()
    logs = []
    
    async for session in get_db():
        stmt = select(User).where(User.id == user_id)
        user = (await session.execute(stmt)).scalar_one_or_none()
        if user and user.role == "curator":
            is_curator = True

        # Check gender from settings
        settings_stmt = select(UserSettings).where(UserSettings.user_id == user_id)
        settings_obj = (await session.execute(settings_stmt)).scalar_one_or_none()
        if settings_obj and settings_obj.gender == "female":
            is_female = True

        # Get daily metrics (calories, macros) for display
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
            "calories": settings_obj.calorie_goal if settings_obj else 2000,
            "water": settings_obj.water_goal if settings_obj else 2000
        }
        
        # 5. Get user subscription for the menu text
        from datetime import datetime
        sub_stmt = select(Subscription).where(Subscription.user_id == user_id)
        sub = (await session.execute(sub_stmt)).scalar_one_or_none()
        
        sub_text_block = "🆓 FREE"
        if sub and sub.is_active:
            tier_icons = {"pro": "💎 PRO", "basic": "🌟 BASIC", "curator": "👑 CURATOR"}
            tier_display = tier_icons.get(sub.tier, "🆓 FREE")
            
            if not sub.expires_at:
                 sub_text_block = f"{tier_display} | Бессрочно ∞"
            else:
                 now_dt = datetime.now()
                 if sub.expires_at < now_dt:
                     sub_text_block = f"{tier_display} (Истекла)"
                 else:
                     diff = sub.expires_at - now_dt
                     if diff.days > 0:
                         sub_text_block = f"{tier_display} | Осталось: {diff.days} дн."
                     else:
                         hours = diff.seconds // 3600
                         sub_text_block = f"{tier_display} | Осталось: {hours} ч."
        
        # 6. Get recent logs for the card
        logs_stmt = select(ConsumptionLog).where(
            and_(
                ConsumptionLog.user_id == user_id,
                func.date(ConsumptionLog.date) == today
            )
        ).order_by(ConsumptionLog.date.desc()).limit(10)
        logs = (await session.execute(logs_stmt)).scalars().all()
        break # One session is enough

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
    
    # Row 3.5: AI Guide
    builder.button(text="🤖 Личный Гид", callback_data="menu_guide")

    # Row 4: System
    builder.button(text="⚙️ Настройки", callback_data="menu_settings")
    builder.button(text="💎 Подписки", callback_data="show_subscriptions")
    builder.button(text="🎁 Рефералка", callback_data="referrals_menu")
    builder.button(text="ℹ️ Справка", callback_data="menu_help")

    # Row 5: Web App
    from aiogram.types import WebAppInfo
    from api.auth import create_access_token
    
    token = create_access_token(data={"sub": user_id})
    vk_app_link = f"https://vk.com/app54530169#token={token}"
    
    builder.button(text="🚀 FoodFlow в VK", url=vk_app_link)
    builder.button(text="📱 App (TG)", web_app=WebAppInfo(url="https://tretyakov-igor.tech/foodflow/"))
    builder.button(text="🔑 Вход в App", callback_data="menu_web_login")


    # Row 6: Contact
    builder.button(text="📩 Написать разработчику", callback_data="menu_contact_dev")

    # Row 6: Admin
    from config import settings
    if message.from_user.id in settings.ADMIN_IDS:
        builder.button(text="🔄 RESTART", callback_data="admin_restart_bot")
        builder.button(text="📨 ЮЗЕРУ", callback_data="admin_send_message")
        builder.button(text="💰 ЗВЕЗДЫ", callback_data="admin_view_stars")
        builder.button(text="🖥️ HEALTH", callback_data="admin_healthcheck")

    # Layout depends on curator status
    if is_curator:
        rows = [2, 1, 1, 1, 2, 1, 3, 3, 2, 1]  # Added row for Guide
    else:
        rows = [2, 1, 1, 1, 2, 1, 3, 2, 1]  # Added row for Guide
    
    if message.from_user.id in settings.ADMIN_IDS:
        # If admin, the last row (Row 6) has 4 buttons now
        rows.append(4)
    
    builder.adjust(*rows)


    # Generate the dynamic dashboard card
    from services.image_renderer import draw_daily_card
    photo_bytes = draw_daily_card(user_name, today, logs, total_metrics, goals, water_total)

    # Use InputMediaPhoto instead of Animation
    media_file = types.BufferedInputFile(photo_bytes.getvalue(), filename="dashboard.png")

    caption = (
        f"🍽️ <b>FoodFlow</b>\n\n"
        f"Привет, <b>{user_name}</b>! 👋\n"
        f"💳 Уровень доступа: <b>{sub_text_block}</b>\n\n"
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
    await callback.answer()
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


@router.callback_query(F.data == "menu_web_login")
async def menu_web_login_handler(callback: types.CallbackQuery) -> None:
    """Show Telegram ID and individual password for web access."""
    from utils.auth_utils import generate_user_password
    from aiogram.types import WebAppInfo

    user_id = callback.from_user.id
    password = generate_user_password(user_id)
    
    # We use a special URL that might pre-fill the data or just the login page
    web_app_url = "https://tretyakov-igor.tech/foodflow/"

    text = (
        "🔐 <b>Данные для входа в App</b>\n\n"
        "Используй эти данные, если заходишь через ярлык на рабочем столе или PWA:\n\n"
        f"👤 <b>Telegram ID:</b> <code>{user_id}</code>\n"
        f"🔑 <b>Пароль:</b> <code>{password}</code>\n\n"
        "☝️ <i>Нажми на ID или Пароль, чтобы скопировать.</i>\n\n"
        "После ввода этих данных браузер запомнит тебя на 30 дней."
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="📱 Открыть App", web_app=WebAppInfo(url=web_app_url))
    builder.button(text="🔙 Назад", callback_data="main_menu")
    builder.adjust(1, 1)

    try:
        # Try to delete original dashboard if it was a photo, to avoid confusion
        # But here it's better to just answer or send new message if it was a photo
        await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        await callback.answer()
    except Exception:
        await callback.answer(text, show_alert=True)


@router.message(Command("web"))
async def web_link_command(message: types.Message) -> None:
    """Generate a magic link for web access without Telegram."""
    from api.auth import create_access_token
    from utils.auth_utils import generate_user_password

    user_id = message.from_user.id
    token = create_access_token(data={"sub": user_id})
    password = generate_user_password(user_id)

    link = f"https://tretyakov-igor.tech/?token={token}"

    text = (
        "🌐 <b>Вход в Web-версию</b>\n\n"
        "1. <b>Быстрый вход</b> (ссылка):</b>\n"
        f"<code>{link}</code>\n\n"
        "2. <b>Прямой вход</b> (для ярлыка):\n"
        f"👤 ID: <code>{user_id}</code>\n"
        f"🔑 Пароль: <code>{password}</code>\n\n"
        "💡 <i>Совет: Сохрани ID и Пароль, они понадобятся, если браузер «забудет» тебя.</i>"
    )

    await message.answer(text, parse_mode="HTML")
