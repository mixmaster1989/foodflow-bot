
"""Herbalife Expert Handler."""

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from services.herbalife_expert import herbalife_expert

router = Router()

@router.callback_query(F.data == "menu_herbalife")
async def show_herbalife_menu(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Show Herbalife main menu."""
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🥤 Конструктор Коктейля", callback_data="hl_shake_builder")
    builder.button(text="💊 Витамины / БАДы", callback_data="hl_supplements")
    builder.button(text="📖 Каталог Продуктов", callback_data="hl_catalog")
    builder.button(text="🔙 Главное меню", callback_data="main_menu")
    builder.adjust(1)
    
    text = (
        "🌿 **Herbalife Expert**\n\n"
        "Я помогу вам правильно использовать продукты Herbalife.\n"
        "Выберите действие:"
    )
    
    try:
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data == "hl_catalog")
async def show_catalog(callback: types.CallbackQuery):
    """Show simple catalog list."""
    # Fetch from JSON DB via expert service
    products = herbalife_expert._db.get("products", [])
    
    text = "📋 **Каталог Продуктов**\n\n"
    for p in products[:15]: # Limit so message isn't too long
        text += f"🔹 {p.get('name', 'Unknown')}\n"
        
    text += "\n_...и другие (введите название в чат)_"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="menu_herbalife")
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data == "hl_shake_builder")
async def shake_builder(callback: types.CallbackQuery):
    """Stub for shake builder."""
    text = (
        "🥤 **Конструктор Коктейля**\n\n"
        "Чтобы записать коктейль, просто напишите мне:\n"
        "`Коктейль 3 ложки дыня 2 ложки белок`\n\n"
        "Я сам посчитаю КБЖУ!"
    )
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="menu_herbalife")
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data == "hl_supplements")
async def supplements_info(callback: types.CallbackQuery):
    """Stub for supplements."""
    text = (
        "💊 **Витамины и БАДы**\n\n"
        "Напишите название витаминов (например 'Желтые таблетки' или 'Термокомплит'), "
        "и я пришлю их состав и как принимать."
    )
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="menu_herbalife")
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()
