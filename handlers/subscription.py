import logging

from aiogram import F, Router, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from database.base import get_db
from database.models import Subscription

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(F.data == "show_subscriptions")
async def show_subscriptions(callback: types.CallbackQuery) -> None:
    """Show details about subscription tiers with purchase buttons."""
    user_id = callback.from_user.id

    # Get current subscription status
    current_tier = "free"
    expires_text = ""
    has_paid_sub = False

    async for session in get_db():
        stmt = select(Subscription).where(Subscription.user_id == user_id)
        sub = (await session.execute(stmt)).scalar_one_or_none()
        if sub and sub.is_active:
            current_tier = sub.tier
            if sub.expires_at:
                expires_text = f"\n⏳ Действует до: <code>{sub.expires_at.strftime('%d.%m.%Y')}</code>"
                if sub.telegram_payment_charge_id:
                    has_paid_sub = True
        break

    # Status badge
    tier_badges = {
        "free": "🌱 Free",
        "basic": "💡 Basic",
        "pro": "🚀 Pro",
        "curator": "👨‍🏫 Curator",
    }
    current_badge = tier_badges.get(current_tier, "🌱 Free")

    text = (
        f"💎 <b>Подписки FoodFlow</b>\n"
        f"Текущий тариф: <b>{current_badge}</b>{expires_text}\n\n"
        "Выбери свой уровень комфорта и контроля:\n\n"

        "🌱 <b>Уровень Free (Бесплатный)</b>\n"
        "• Ручной ввод текстом (по 1 продукту)\n"
        "• Трекинг воды и веса\n"
        "• Базовый дашборд\n"
        "• Максимум 3 сохраненных блюда\n\n"

        "💡 <b>Уровень Basic — 199 ₽/мес</b>\n"
        "• <i>Всё из уровня Free, плюс:</i>\n"
        "• 📝 Запись всей еды одной фразой (Batch Mode)\n"
        "• 🎙 Голосовой ввод еды (безлимит)\n"
        "• 🧊 Умный Холодильник\n"
        "• 🔔 Гибкие уведомления\n"
        "• 📈 Подробная статистика и графики\n"
        "• 📖 Безлимит на сохраненные рецепты\n\n"

        "🚀 <b>Уровень Pro — 299 ₽/мес</b>\n"
        "• <i>Всё из уровня Basic, плюс:</i>\n"
        "• 📸 Анализ фото еды (КБЖУ по фото)\n"
        "• 🧾 Сканер чеков (авто-холодильник)\n"
        "• 👨‍🍳 Подбор рецептов из того, что есть в холодильнике\n"
        "• 👩‍⚕️ Ежедневный разбор от Нейро-нутрициолога\n\n"

        "👨‍🏫 <b>Уровень Куратор — 499 ₽/мес</b>\n"
        "• <i>Всё из уровня Pro, плюс:</i>\n"
        "• 👥 Кабинет куратора для ведения подопечных\n"
        "• 📊 Детальные отчёты и марафоны\n\n"

        "<i>Оплата картой (RUB) или через Telegram Stars ⭐.</i>"

    )

    builder = InlineKeyboardBuilder()

    # Show buy buttons only for tiers above current
    tier_order = ["free", "basic", "pro", "curator"]
    current_idx = tier_order.index(current_tier) if current_tier in tier_order else 0

    if current_idx < 1:
        builder.button(text="💡 Купить Basic", callback_data="buy_tier:basic")
    if current_idx < 2:
        builder.button(text="🚀 Купить Pro", callback_data="buy_tier:pro")
    if current_idx < 3:
        builder.button(text="👨‍🏫 Купить Куратор", callback_data="buy_tier:curator")

    # Cancel button for paid users
    if has_paid_sub:
        builder.button(text="🔕 Отменить подписку", callback_data="cancel_subscription")

    builder.button(text="🔙 Главное меню", callback_data="main_menu")
    builder.adjust(1)

    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    except Exception:
        try:
            await callback.message.edit_caption(caption=text, parse_mode="HTML", reply_markup=builder.as_markup())
        except Exception:
            await callback.message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()
