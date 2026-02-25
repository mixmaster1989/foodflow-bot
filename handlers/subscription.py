from aiogram import Router, types, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
import logging

router = Router()
logger = logging.getLogger(__name__)

@router.callback_query(F.data == "show_subscriptions")
async def show_subscriptions(callback: types.CallbackQuery) -> None:
    """Show details about subscription tiers."""
    
    text = (
        "💎 <b>Подписки FoodFlow</b>\n\n"
        "Выбери свой уровень комфорта и контроля:\n\n"
        "🌱 <b>Уровень Free (Бесплатный)</b>\n"
        "• Ручной ввод текстом\n"
        "• Трекинг воды и веса\n"
        "• Базовый дашборд\n"
        "• Максимум 3 сохраненных блюда\n\n"
        
        "💡 <b>Уровень Basic (Оптимизатор)</b>\n"
        "• <i>Всё из уровня Free, плюс:</i>\n"
        "• 🎙 Голосовой ввод еды (безлимит)\n"
        "• 🧊 Умный Холодильник\n"
        "• 🔔 Гибкие уведомления\n"
        "• 📈 Подробная статистика и графики\n"
        "• 📖 Безлимит на сохраненные рецепты\n\n"
        
        "🚀 <b>Уровень Pro (Нейро-максимум)</b>\n"
        "• <i>Всё из уровня Basic, плюс:</i>\n"
        "• 📸 Анализ фото еды (КБЖУ по фото)\n"
        "• 🧾 Сканер чеков (авто-холодильник)\n"
        "• 👨‍🍳 Подбор рецептов из того, что есть в холодильнике\n"
        "• 👩‍⚕️ Ежедневный разбор от Нейро-нутрициолога\n\n"
        
        "<i>Подключение оплаты находится в разработке...</i>\n"
        "<b>А пока мы дарим тебе тариф PRO абсолютно бесплатно!</b> 🎉"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Понятно", callback_data="main_menu")
    builder.adjust(1)
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()
