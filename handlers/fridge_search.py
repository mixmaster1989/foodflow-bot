"""
Module for Smart Fridge Search.

Implements fuzzy search, pagination, and AI-ready filtering.
"""
import json
import logging
import math

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import or_, select

from database.base import get_db
from database.models import Product, Receipt
from services.kbju_core import KBJUCoreService

# Placeholder for future AI Brain integration
# from services.ai_brain import AIBrainService

router = Router()
logger = logging.getLogger(__name__)

PAGE_SIZE = 10

@router.callback_query(F.data == "fridge_search")
async def fridge_search_start(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Start fridge search - with AI Summary."""
    from datetime import datetime, timedelta

    from database.models import UserSettings
    from handlers.fridge import FridgeStates
    from services.ai_brain import AIBrainService

    await state.set_state(FridgeStates.searching_fridge)

    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="menu_fridge")

    initial_text = "⏳ <b>Заглядываю в холодильник...</b>"

    try:
        await callback.message.edit_caption(caption=initial_text, parse_mode="HTML", reply_markup=builder.as_markup())
    except Exception:
        try:
            await callback.message.edit_text(initial_text, parse_mode="HTML", reply_markup=builder.as_markup())
        except Exception:
            await callback.message.answer(initial_text, parse_mode="HTML", reply_markup=builder.as_markup())

    # 1. Fetch Products
    user_id = callback.from_user.id

    async for session in get_db():
        # Get Settings & Cache
        settings_stmt = select(UserSettings).where(UserSettings.user_id == user_id)
        user_settings = (await session.execute(settings_stmt)).scalar_one_or_none()

        # Check Cache
        cached_data = None
        if user_settings and user_settings.fridge_summary_cache and user_settings.fridge_summary_date:
            if datetime.now() - user_settings.fridge_summary_date < timedelta(hours=24):
                cached_data = user_settings.fridge_summary_cache

        summary_text = ""
        tags = []

        if cached_data:
            # Try to parse JSON (new format) or use as text (legacy)
            try:
                data = json.loads(cached_data)
                summary_text = data.get("summary", "")
                tags = data.get("tags", [])
                logger.info(f"[AI Summary] Cache HIT for user {user_id}. Tags: {len(tags)}")
            except json.JSONDecodeError:
                summary_text = cached_data # Legacy plain text
                logger.info(f"[AI Summary] Cache HIT (Legacy Text) for user {user_id}")
        else:
            # Generate New Summary
            stmt = (
                select(Product.name)
                .outerjoin(Receipt)
                .where(or_(Receipt.user_id == user_id, Product.user_id == user_id))
                .order_by(Product.id.desc())
                .limit(40)
            )
            products = (await session.execute(stmt)).scalars().all()

            if not products:
                summary_text = "В холодильнике пустовато... Самое время что-то купить! 🛒"
                logger.info(f"[AI Summary] Empty fridge for user {user_id}")
            else:
                try:
                    logger.info(f"[AI Summary] Generating for user {user_id}, items: {len(products)}")
                    result = await AIBrainService.summarize_fridge(list(products))
                    if result:
                        # Handle Dict or String result
                        if isinstance(result, dict):
                            summary_text = result.get("summary", "")
                            tags = result.get("tags", [])
                            cache_val = json.dumps(result, ensure_ascii=False)
                        else:
                            summary_text = result
                            cache_val = result # Legacy fallback


                        # Update Cache
                        if user_settings:
                            user_settings.fridge_summary_cache = cache_val
                            user_settings.fridge_summary_date = datetime.now()
                            session.add(user_settings)
                            await session.commit()
                            logger.info(f"[AI Summary] Cache UPDATED for user {user_id}")
                except Exception as e:
                    logger.error(f"[AI Summary] Failed for {user_id}: {e}")
                    summary_text = "Не удалось провести ревизию, но вы можете найти продукты ниже."

    # Render
    text = f"🤖 {summary_text}\n\n" if summary_text else ""
    text += "🔍 <b>Поиск по холодильнику</b>\n"
    text += "Введите название продукта или выберите тег:"

    # Add Tag Buttons
    if tags:
        for tag_item in tags:
            if isinstance(tag_item, dict):
                # New format: {"tag": "Milk", "emoji": "🥛"}
                t_val = tag_item.get("tag", "Tag")
                emoji = tag_item.get("emoji", "🔍")
                btn_text = f"{emoji} {t_val}"
                callback_val = t_val
            else:
                # Old format: string
                btn_text = f"🔍 {tag_item}"
                callback_val = tag_item

            builder.button(text=btn_text, callback_data=f"fridge_search_tag:{callback_val}")
        builder.adjust(2) # 2 tags per row

    builder.row(types.InlineKeyboardButton(text="❌ Отмена", callback_data="menu_fridge"))

    try:
        await callback.message.edit_caption(caption=text, parse_mode="HTML", reply_markup=builder.as_markup())
    except Exception:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())

    await callback.answer()


    await callback.answer()

@router.callback_query(F.data.startswith("fridge_search_tag:"))
async def fridge_search_tag_handler(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Handle click on AI search tag."""
    tag = callback.data.split(":")[1]
    await state.update_data(search_query=tag)
    await show_search_results(callback.message, state, page=0, is_edit=True)
    await callback.answer()

@router.callback_query(F.data == "fridge_search_back")
async def fridge_search_back_handler(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Handle 'Back' from product detail to search results."""
    data = await state.get_data()
    page = data.get("search_page", 0)
    await show_search_results(callback.message, state, page=page, is_edit=True, use_session_query=True)
    await callback.answer()


# Import FridgeStates for state filtering
from handlers.fridge import FridgeStates


@router.message(FridgeStates.searching_fridge, F.text, lambda msg: msg.text and len(msg.text) > 1)
async def fridge_search_query(message: types.Message, state: FSMContext) -> None:
    """Handle search query input - ONLY in searching_fridge state."""

    query = message.text.strip()
    await state.update_data(search_query=query)
    await show_search_results(message, state, page=0)


@router.callback_query(F.data.startswith("fridge_search_page:"))
async def fridge_search_pagination(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Handle pagination for search results."""
    try:
        page = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        page = 0

    await state.update_data(search_page=page)
    await show_search_results(callback.message, state, page=page, is_edit=True, use_session_query=True)
    await callback.answer()


async def show_search_results(message: types.Message, state: FSMContext, page: int = 0, is_edit: bool = False, use_session_query: bool = False) -> None:
    """Render search results with pagination."""

    data = await state.get_data()
    query = data.get("search_query", "")
    user_id = message.chat.id

    if not query:
        await message.answer("⚠️ Ошибка поиска: пустой запрос.")
        return

        # 1. Smart Search Logic (Python-side filtering)
        keywords = query.lower().split()
        
        # 🚀 IMPROVEMENT: Use KBJUCore for query normalization
        core_query = await KBJUCoreService.get_product_nutrition(query, session)
        base_query = core_query.base_name.lower() if core_query.base_name else ""

        # Fetch ALL products for user
        stmt = select(Product).outerjoin(Receipt).where(
            or_(Receipt.user_id == user_id, Product.user_id == user_id)
        ).order_by(Product.id.desc())

        all_products = (await session.execute(stmt)).scalars().all()

        # Filter in Python
        filtered_products = []
        for p in all_products:
            name_norm = p.name.lower()
            p_base_name = p.base_name.lower() if p.base_name else ""
            
            # Match if:
            # 1. ALL keywords are in name
            # 2. OR base_name matches base_query
            if all(kw in name_norm for kw in keywords) or (base_query and base_query in p_base_name):
                filtered_products.append(p)

        total_items = len(filtered_products)

        # Pagination in Python
        start_idx = page * PAGE_SIZE
        end_idx = start_idx + PAGE_SIZE
        products = filtered_products[start_idx:end_idx]

        logger.info(f"[Search Debug] Query: '{query}', Results: {len(products)}, Total: {total_items} (from {len(all_products)} items)")

    # 2. Render Response
    builder = InlineKeyboardBuilder()

    if total_items == 0:
        text = (
            f"🔍 По запросу <b>«{query}»</b> ничего не найдено.\n\n"
            "Попробуйте другой запрос (например, часть слова)."
        )
        builder.button(text="🔍 Искать снова", callback_data="fridge_search")
        builder.button(text="🔙 В холодильник", callback_data="menu_fridge")
        builder.adjust(1)

        if is_edit:
            await message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
        else:
            await message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
        return

    # 3. Build List
    total_pages = math.ceil(total_items / PAGE_SIZE)
    # Ensure page is valid
    if page >= total_pages:
        page = total_pages - 1
    if page < 0:
        page = 0

    text = f"🔍 <b>Результаты поиска: «{query}»</b>\n"
    text += f"Найдено: {total_items} (Стр. {page+1}/{total_pages})\n\n"

    for p in products:
        cal_info = f"({int(p.calories)} ккал)" if p.calories else ""
        # 🚀 SOURCE FLAG: 1 = Search
        builder.button(text=f"📦 {p.name[:20]} {cal_info}", callback_data=f"fridge_item:{p.id}:{page}:1")

    builder.adjust(1)

    # Navigation
    nav_buttons = []
    if page > 0:
        nav_buttons.append(types.InlineKeyboardButton(text="⬅️", callback_data=f"fridge_search_page:{page-1}"))

    nav_buttons.append(types.InlineKeyboardButton(text=f"📄 {page+1}/{total_pages}", callback_data="noop"))

    if page < total_pages - 1:
        nav_buttons.append(types.InlineKeyboardButton(text="➡️", callback_data=f"fridge_search_page:{page+1}"))

    builder.row(*nav_buttons)

    builder.row(types.InlineKeyboardButton(text="🔍 Искать снова", callback_data="fridge_search"))
    builder.row(types.InlineKeyboardButton(text="🔙 В холодильник", callback_data="menu_fridge"))

    if is_edit:
        await message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())

