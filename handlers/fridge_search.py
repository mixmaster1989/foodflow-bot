"""
Module for Smart Fridge Search.

Implements fuzzy search, pagination, and AI-ready filtering.
"""
import logging
import math
from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, or_, and_
from sqlalchemy.orm import selectinload

from database.base import get_db
from database.models import Product, Receipt
# Placeholder for future AI Brain integration
# from services.ai_brain import AIBrainService 

router = Router()
logger = logging.getLogger(__name__)

PAGE_SIZE = 10

@router.callback_query(F.data == "fridge_search")
async def fridge_search_start(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Start fridge search - ask for search query."""
    from handlers.fridge import FridgeStates # Reuse states or create new
    
    await state.set_state(FridgeStates.searching_fridge)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="menu_fridge")
    
    text = (
        "🔍 <b>Поиск по холодильнику</b>\n\n"
        "Введите название продукта (например: <i>молоко, курица, хлеб</i>):"
    )
    
    try:
        await callback.message.edit_caption(caption=text, parse_mode="HTML", reply_markup=builder.as_markup())
    except Exception:
        try:
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
        except Exception:
            await callback.message.delete()
            await callback.message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()


@router.message(F.text, lambda msg: msg.text and len(msg.text) > 1) 
# Note: State filter should be applied in main registration or here if importing states
async def fridge_search_query(message: types.Message, state: FSMContext) -> None:
    """Handle search query input."""
    
    # Verify state (since we can't easily import FridgeStates here without circular imports if not careful)
    # Ideally, we should move States to a shared module. For now, we assume this handler is registered with the correct state filter in main.py
    
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
        
    await show_search_results(callback.message, state, page=page, is_edit=True)
    await callback.answer()


async def show_search_results(message: types.Message, state: FSMContext, page: int = 0, is_edit: bool = False) -> None:
    """Render search results with pagination."""
    
    data = await state.get_data()
    query = data.get("search_query", "")
    user_id = message.chat.id # Fallback if message.from_user is None
    if message.from_user:
        user_id = message.from_user.id
        
    if not query:
        await message.answer("⚠️ Ошибка поиска: пустой запрос.")
        return

    # 1. Smart Search Logic
    # Split query into keywords for AND logic
    keywords = query.lower().split()
    
    async for session in get_db():
        # Base query
        stmt = select(Product).outerjoin(Receipt).where(
            or_(Receipt.user_id == user_id, Product.user_id == user_id)
        )
        
        # Add ILIKE filter for EACH keyword (AND logic)
        # This allows "chicken file" to match "Filet Chicken"
        if keywords:
            filters = []
            for kw in keywords:
                filters.append(Product.name.ilike(f"%{kw}%"))
            stmt = stmt.where(and_(*filters))
            
        # Count total results
 
        # Actually proper way to count with complex query:
        # We'll just fetch all for now or improve count query later. 
        # For SQLite, fetching all IDs first is fast enough for small fridge.
        
        # Let's use a simpler approach for accuracy: fetch logic first, then slice in python or use pagination sql
        # Better: use proper Count query
        
        # Correct Count Query
        # Reconstruct the where clause for counting
        # This is tricky with SQLAlchemy imperative style. 
        # Let's simply execute the main query with limit/offset
        
        # We need total count for pagination
        # Let's perform a count query first
        count_q = select(func.count()).select_from(Product).outerjoin(Receipt).where(
             or_(Receipt.user_id == user_id, Product.user_id == user_id)
        )
        if keywords:
             for kw in keywords:
                 count_q = count_q.where(Product.name.ilike(f"%{kw}%"))
                 
        total_items = await session.scalar(count_q) or 0
        
        # Get Page Items
        stmt = stmt.order_by(Product.id.desc()).offset(page * PAGE_SIZE).limit(PAGE_SIZE)
        products = (await session.execute(stmt)).scalars().all()

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
    if page >= total_pages: page = total_pages - 1
    if page < 0: page = 0
    
    text = f"🔍 <b>Результаты поиска: «{query}»</b>\n"
    text += f"Найдено: {total_items} (Стр. {page+1}/{total_pages})\n\n"
    
    for p in products:
        cal_info = f"({int(p.calories)} ккал)" if p.calories else ""
        # FIXED: Callback uses fridge_item, not fridge_product
        builder.button(text=f"📦 {p.name[:20]} {cal_info}", callback_data=f"fridge_item:{p.id}:0")
        
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

from sqlalchemy import func
