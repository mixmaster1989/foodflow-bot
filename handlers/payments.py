"""Telegram Stars Payments handler.

Handles the complete payment flow for FoodFlow subscriptions:
- Creating invoice links for Basic / Pro / Curator tiers
- Pre-checkout validation
- Successful payment processing
- Subscription cancellation and refunds
- Mandatory /paysupport and /terms commands
"""
import logging
from datetime import datetime, timedelta

from aiogram import Bot, F, Router, types
from aiogram.filters import Command
from aiogram.types import LabeledPrice
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from config import settings
from database.base import get_db
from database.models import (
    PAYMENT_SOURCE_STARS,
    PAYMENT_SOURCE_YOOKASSA,
    Subscription,
)
from services.referral_service import ReferralService
from services.payment_service import YooKassaService

logger = logging.getLogger(__name__)
router = Router()

# --- Tier Configuration ---
TIERS = {
    "basic": {
        "title": "FoodFlow Basic — 30 дней",
        "description": (
            "• 📝 Запись всей еды одной фразой (Batch Mode)\n"
            "• 🎙 Голосовой ввод (безлимит)\n"
            "• 🧊 Умный Холодильник\n"
            "• 🔔 Гибкие уведомления\n"
            "• 📈 Подробная статистика"
        ),
        "price_stars": 130,
        "price_rub": 199,
        "emoji": "💡",
    },
    "pro": {
        "title": "FoodFlow Pro — 30 дней",
        "description": (
            "• Всё из Basic, плюс:\n"
            "• 📸 AI-анализ фото еды\n"
            "• 🧾 Сканер чеков\n"
            "• 👨‍🍳 Подбор рецептов из холодильника\n"
            "• 👩‍⚕️ Ежедневный отчёт нейро-нутрициолога"
        ),
        "price_stars": 200,
        "price_rub": 299,
        "emoji": "🚀",
    },
    "curator": {
        "title": "FoodFlow Куратор — 30 дней",
        "description": (
            "• Всё из Pro, плюс:\n"
            "• 👥 Кабинет куратора\n"
            "• 📊 Отчёты по подопечным\n"
            "• 🔗 Реферальные ссылки\n"
            "• 🏆 Марафоны и геймификация"
        ),
        "price_stars": 350,
        "price_rub": 499, # Пропорционально звездам
        "emoji": "👨‍🏫",
    },
}

SUBSCRIPTION_PERIOD = 2592000  # 30 days in seconds (Telegram requirement)

# --- Duration options for one-time purchases ---
DURATIONS = {
    1:  {"months": 1,  "label": "1 мес",     "discount": 0.0,  "emoji": "1️⃣"},
    3:  {"months": 3,  "label": "3 мес",     "discount": 0.10, "emoji": "📦"},
    6:  {"months": 6,  "label": "6 мес",     "discount": 0.15, "emoji": "🎁"},
    12: {"months": 12, "label": "12 мес",    "discount": 0.20, "emoji": "🏆"},
}


def calc_price(base_monthly: int, months: int, discount: float) -> int:
    """Calculate discounted price, rounded to nearest integer."""
    return round(base_monthly * months * (1 - discount))


def int_to_emoji(n: int) -> str:
    """Convert an integer to a string of Telegram emoji digits."""
    mapping = {
        '0': '0️⃣', '1': '1️⃣', '2': '2️⃣', '3': '3️⃣', '4': '4️⃣',
        '5': '5️⃣', '6': '6️⃣', '7': '7️⃣', '8': '8️⃣', '9': '9️⃣'
    }
    return "".join(mapping[c] for c in str(n))

# =====================================================
# Invoice Creation — Step 1: Choose currency and payment type
# =====================================================

@router.callback_query(F.data.startswith("buy_tier:"))
async def handle_choose_payment_type(callback: types.CallbackQuery):
    """Show choice: Stars vs RUB."""
    tier = callback.data.split(":")[1]

    if tier not in TIERS:
        await callback.answer("❌ Неизвестный тариф", show_alert=True)
        return

    tier_info = TIERS[tier]
    price_stars = tier_info["price_stars"]
    price_rub = tier_info["price_rub"]

    builder = InlineKeyboardBuilder()
    
    # Currency Selection
    builder.button(
        text="⭐ Оплатить через Stars",
        callback_data=f"stars_choice:{tier}",
    )
    builder.button(
        text="💳 Оплатить Картой (RUB)",
        callback_data=f"buy_once:{tier}:RUB",
    )
    
    builder.button(text="🔙 Назад к тарифам", callback_data="show_subscriptions")
    builder.adjust(1)

    text = (
        f"{tier_info['emoji']} <b>{tier_info['title']}</b>\n\n"
        f"{tier_info['description']}\n\n"
        f"💰 Стоимость:\n"
        f"— <b>{price_stars} ⭐ Stars</b>\n"
        f"— <b>{price_rub} ₽ (Карта)</b>\n\n"
        "Выберите способ оплаты:"
    )

    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("stars_choice:"))
async def handle_stars_choice(callback: types.CallbackQuery):
    """Show choice: Auto-renew vs One-time for Stars."""
    tier = callback.data.split(":")[1]
    tier_info = TIERS[tier]
    price_stars = tier_info["price_stars"]

    builder = InlineKeyboardBuilder()
    builder.button(
        text=f"🔄 Автопродление — {price_stars} ⭐",
        callback_data=f"buy_sub:{tier}",
    )
    builder.button(
        text=f"1️⃣ Разовая оплата — {price_stars} ⭐",
        callback_data=f"buy_once:{tier}:XTR",
    )
    builder.button(text="🔙 Назад", callback_data=f"buy_tier:{tier}")
    builder.adjust(1)

    text = (
        f"⭐ <b>Оплата через Stars: {tier_info['title']}</b>\n\n"
        "Выберите тип оплаты:\n"
        "• <b>Автопродление</b> — подписка будет продлеваться автоматически каждый месяц.\n"
        "• <b>Разовая оплата</b> — доступ на выбранный срок без автосписаний (доступны скидки при покупке на несколько месяцев)."
    )

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()
    await callback.answer()



# =====================================================
# Invoice Creation — Step 2a: Auto-renewing subscription
# =====================================================

@router.callback_query(F.data.startswith("buy_sub:"))
async def handle_buy_subscription(callback: types.CallbackQuery, bot: Bot):
    """Create an invoice link WITH auto-renewal (subscription_period)."""
    tier = callback.data.split(":")[1]
    if tier not in TIERS:
        await callback.answer("❌ Неизвестный тариф", show_alert=True)
        return

    tier_info = TIERS[tier]
    user_id = callback.from_user.id

    # Admin test mode: for admins in beta, subscriptions cost 1 Star
    is_admin_test = settings.IS_BETA_TESTING and user_id in settings.ADMIN_IDS
    price_stars = 1 if is_admin_test else tier_info["price_stars"]

    try:
        link = await bot.create_invoice_link(
            title=tier_info["title"],
            description=tier_info["description"] + "\n🔄 Автопродление",
            payload=f"sub_{tier}_{user_id}",
            currency="XTR",
            prices=[LabeledPrice(label=tier_info["title"], amount=price_stars)],
            subscription_period=SUBSCRIPTION_PERIOD,
        )

        builder = InlineKeyboardBuilder()
        builder.button(text=f"⭐ Оплатить {price_stars} Stars", url=link)
        builder.button(text="🔙 Назад", callback_data=f"buy_tier:{tier}")
        builder.adjust(1)

        text = (
            f"{tier_info['emoji']} <b>{tier_info['title']}</b>\n\n"
            f"💰 <b>{price_stars} ⭐</b> / мес.\n"
            f"🔄 Автопродление каждые 30 дней\n"
            f"🔕 Можно отменить в любой момент через меню подписок\n\n"
            f"<i>Нажмите кнопку ниже для оплаты:</i>"
        )

        try:
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
        except Exception:
            await callback.message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())

    except Exception as e:
        logger.error(f"Failed to create subscription invoice for {tier}: {e}")
        await callback.answer("❌ Ошибка создания счёта. Попробуйте позже.", show_alert=True)
    await callback.answer()


# =====================================================
# Invoice Creation — Step 2b: Choose duration (one-time)
# =====================================================

@router.callback_query(F.data.startswith("buy_once:"))
async def handle_choose_duration(callback: types.CallbackQuery):
    """Show duration options with discounts for one-time purchase."""
    parts = callback.data.split(":")
    if len(parts) < 3:
        await callback.answer("❌ Ошибка параметров", show_alert=True)
        return
        
    tier = parts[1]
    currency = parts[2] # "XTR" or "RUB"
    
    if tier not in TIERS:
        await callback.answer("❌ Неизвестный тариф", show_alert=True)
        return

    tier_info = TIERS[tier]
    base = tier_info["price_rub"] if currency == "RUB" else tier_info["price_stars"]
    curr_symbol = "₽" if currency == "RUB" else "⭐"

    builder = InlineKeyboardBuilder()
    lines = []

    for months, dur in DURATIONS.items():
        total = calc_price(base, months, dur["discount"])
        full_price = base * months  # price without discount
        savings = full_price - total
        per_month = total // months

        total_label = f"{total} {curr_symbol}"

        if dur["discount"] == 0:
            # 1 month — no discount
            builder.button(
                text=f"{dur['emoji']} {dur['label']} — {total_label}",
                callback_data=f"buy_once_dur:{tier}:{months}:{currency}",
            )
            lines.append(
                f"{dur['emoji']} <b>{dur['label']}</b> — <b>{total_label}</b>"
            )
        else:
            # Discounted
            pct = int(dur["discount"] * 100)
            best = " 🔥 ЛУЧШАЯ ЦЕНА" if months == 12 else ""
            builder.button(
                text=f"{dur['emoji']} {dur['label']} — {total_label} (-{pct}%){best}",
                callback_data=f"buy_once_dur:{tier}:{months}:{currency}",
            )
            lines.append(
                f"{dur['emoji']} <b>{dur['label']}</b>: <b>{total_label}</b> "
                f"вместо <s>{full_price}{curr_symbol}</s>\n"
                f"     💡 <b>{per_month}{curr_symbol}/мес</b> вместо <s>{base}{curr_symbol}/мес</s>\n"
                f"     💸 Выгода: <b>{savings}{curr_symbol}</b>!{best}"
            )

    builder.button(text="🔙 Назад", callback_data=f"buy_tier:{tier}")
    builder.adjust(1)

    text = (
        f"{tier_info['emoji']} <b>{tier_info['title']}</b>\n"
        f"Разовая оплата ({currency}) · без автосписания\n\n"
        + "\n\n".join(lines) + "\n\n"
        "✅ <i>Оплата один раз — ничего не списывается автоматически</i>"
    )

    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()


# =====================================================
# Invoice Creation — Step 3: Create invoice for chosen duration
# =====================================================

@router.callback_query(F.data.startswith("buy_once_dur:"))
async def handle_buy_once_duration(callback: types.CallbackQuery, bot: Bot):
    """Create a one-time invoice for the selected tier, duration, and currency."""
    parts = callback.data.split(":")
    if len(parts) != 4:
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    tier = parts[1]
    months = int(parts[2])
    currency = parts[3] # "XTR" or "RUB"

    if tier not in TIERS or months not in DURATIONS:
        await callback.answer("❌ Неизвестный тариф или срок", show_alert=True)
        return

    tier_info = TIERS[tier]
    dur = DURATIONS[months]
    
    base_price = tier_info["price_rub"] if currency == "RUB" else tier_info["price_stars"]
    total_price = calc_price(base_price, months, dur["discount"])
    user_id = callback.from_user.id

    # Admin test mode: for admins in beta, any tier/months cost 1 (₽ or Star)
    is_admin_test = settings.IS_BETA_TESTING and user_id in settings.ADMIN_IDS
    if is_admin_test:
        admin_total_price = 1
        logger.info(
            f"[ADMIN_TEST] Overriding price to 1 for user={user_id}, "
            f"tier={tier}, months={months}, currency={currency}, "
            f"base_price={base_price}, calc_price={total_price}"
        )
        total_price = admin_total_price
    else:
        logger.info(
            f"[INVOICE] user={user_id}, tier={tier}, months={months}, "
            f"currency={currency}, base_price={base_price}, total_price={total_price}"
        )

    discount_text = f" (скидка {int(dur['discount']*100)}%)" if dur["discount"] > 0 else ""
    title = f"{tier_info['title']} — {dur['label']}"

    try:
        if currency == "RUB":
            # Direct YooKassa SDK Integration
            metadata = {
                "user_id": user_id,
                "tier": tier,
                "months": months,
                "type": "one-time"
            }
            
            # Get bot info for return url
            bot_info = await bot.get_me()
            return_url = f"https://t.me/{bot_info.username}"
            
            payment = await YooKassaService.create_payment(
                amount=total_price,
                description=f"{title} for user {user_id}",
                metadata=metadata,
                return_url=return_url
            )
            
            if not payment:
                await callback.answer("❌ Ошибка создания платежа в ЮKassa", show_alert=True)
                return
                
            link = payment.confirmation.confirmation_url
            payment_id = payment.id
        else:
            # For XTR (Stars)
            link = await bot.create_invoice_link(
                title=title,
                description=(
                    tier_info["description"]
                    + f"\n📅 Доступ на {months} мес.{discount_text}"
                    + "\n⭐ Оплата Stars (Разово)"
                ),
                payload=f"once_{tier}_{months}_{user_id}_XTR",
                currency="XTR",
                prices=[LabeledPrice(label=title, amount=total_price)],
            )
            payment_id = None

        builder = InlineKeyboardBuilder()
        btn_text = f"💳 Оплатить {total_price} ₽" if currency == "RUB" else f"⭐ Оплатить {total_price} Stars"
        builder.button(text=btn_text, url=link)
        
        if currency == "RUB" and payment_id:
            builder.button(text="✅ Проверить оплату", callback_data=f"check_pay:{payment_id}")
            
        builder.button(text="🔙 Назад", callback_data=f"buy_once:{tier}:{currency}")
        builder.adjust(1)

        text = (
            f"{tier_info['emoji']} <b>{title}</b>\n\n"
            f"💰 <b>{total_price} {'₽' if currency == 'RUB' else '⭐'}</b>{discount_text}\n"
            f"📅 Доступ на {months} мес., без автосписания\n"
            f"✅ Ничего не спишется автоматически\n\n"
            f"<i>Нажмите кнопку ниже для оплаты:</i>"
        )

        try:
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
        except Exception:
            await callback.message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())

    except Exception as e:
        logger.error(f"Failed to create {currency} invoice for {tier}/{months}m: {e}")
        await callback.answer("❌ Ошибка создания счёта. Попробуйте позже.", show_alert=True)
    await callback.answer()


# =====================================================
# YooKassa Status Check
# =====================================================

@router.callback_query(F.data.startswith("check_pay:"))
async def handle_check_yookassa_payment(callback: types.CallbackQuery):
    """Check the status of a YooKassa payment and activate subscription if paid."""
    payment_id = callback.data.split(":")[1]
    
    payment = await YooKassaService.check_payment_status(payment_id)
    
    if not payment:
        await callback.answer("❌ Ошибка при проверке статуса платежа.", show_alert=True)
        return
        
    if payment.status == "succeeded":
        # Payment is successful!
        metadata = payment.metadata
        user_id = int(metadata.get("user_id"))
        tier = metadata.get("tier")
        months = int(metadata.get("months", 1))
        logger.info(
            f"✅ YooKassa payment {payment_id} succeeded for user {user_id}, "
            f"tier={tier}, months={months}, amount={payment.amount.value} {payment.amount.currency}"
        )
        
        # Calculate expiry
        now = datetime.now()
        expires = now + timedelta(days=30 * months)
        
        # Update DB
        async for session in get_db():
            stmt = select(Subscription).where(Subscription.user_id == user_id)
            sub = (await session.execute(stmt)).scalar_one_or_none()

            if sub:
                sub.tier = tier
                sub.starts_at = now
                sub.expires_at = expires
                sub.is_active = True
                sub.auto_renew = False
                sub.telegram_payment_charge_id = None
                sub.payment_source = PAYMENT_SOURCE_YOOKASSA
                sub.yookassa_payment_id = payment_id
            else:
                sub = Subscription(
                    user_id=user_id,
                    tier=tier,
                    starts_at=now,
                    expires_at=expires,
                    is_active=True,
                    auto_renew=False,
                    payment_source=PAYMENT_SOURCE_YOOKASSA,
                    yookassa_payment_id=payment_id,
                )
                session.add(sub)

            await session.commit()
            break

        # Referral bonuses (RUB payments)
        try:
            await ReferralService.handle_successful_payment(user_id=user_id, tier=tier)
        except Exception as e:
            logger.error(f"[REFERRAL] Failed to handle referral bonuses for YooKassa payment {payment_id}: {e}", exc_info=True)
            
        tier_info = TIERS.get(tier, {"title": tier, "emoji": "💎"})
        dur_label = DURATIONS.get(months, {}).get("label", f"{months} мес")
        
        await callback.message.edit_text(
            f"🎉 <b>Оплата подтверждена!</b>\n\n"
            f"Тариф: {tier_info.get('emoji', '')} <b>{tier_info['title']}</b>\n"
            f"Период: <b>{dur_label}</b>\n"
            f"Действует до: <code>{expires.strftime('%d.%m.%Y')}</code>\n\n"
            f"Спасибо за поддержку FoodFlow! 💚",
            parse_mode="HTML"
        )
        await callback.answer("Подписка активирована!", show_alert=True)
        
    elif payment.status == "pending":
        await callback.answer("⏳ Оплата еще в процессе. Попробуйте проверить через минуту.", show_alert=True)
    elif payment.status == "waiting_for_capture":
        await callback.answer("⏳ Оплата ожидает подтверждения.", show_alert=True)
    elif payment.status == "canceled":
        await callback.message.edit_text("❌ Платеж был отменен. Попробуйте еще раз.")
        await callback.answer()
    else:
        await callback.answer(f"Статус платежа: {payment.status}", show_alert=True)



# =====================================================
# Pre-Checkout Query
# =====================================================

@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: types.PreCheckoutQuery):
    """Validate the order before payment is finalized.

    Must respond within 10 seconds or transaction is cancelled.
    """
    payload = pre_checkout_query.invoice_payload

    # Basic validation: payload should start with "sub_" or "once_"
    if not payload.startswith(("sub_", "once_")):
        await pre_checkout_query.answer(
            ok=False,
            error_message="Неверный формат заказа. Попробуйте ещё раз."
        )
        return

    # Extract tier from payload
    parts = payload.split("_")
    if len(parts) < 3 or parts[1] not in TIERS:
        await pre_checkout_query.answer(
            ok=False,
            error_message="Неизвестный тариф. Попробуйте ещё раз."
        )
        return

    # All good — accept the payment
    await pre_checkout_query.answer(ok=True)
    logger.info(f"Pre-checkout approved for user {pre_checkout_query.from_user.id}, payload: {payload}")


# =====================================================
# Successful Payment
# =====================================================

@router.message(F.successful_payment)
async def successful_payment_handler(message: types.Message):
    """Process successful payment: activate or upgrade subscription."""
    payment = message.successful_payment
    payload = payment.invoice_payload
    user_id = message.from_user.id
    charge_id = payment.telegram_payment_charge_id

    # Determine payment type from payload prefix
    is_subscription = payload.startswith("sub_")

    # Parse payload: sub_tier_uid or once_tier_months_uid
    parts = payload.split("_")

    if is_subscription:
        # sub_basic_432823154
        if len(parts) < 3:
            logger.error(f"Invalid payment payload: {payload}")
            return
        tier = parts[1]
        months = 1
    else:
        # once_basic_3_432823154
        if len(parts) < 4:
            logger.error(f"Invalid payment payload: {payload}")
            return
        tier = parts[1]
        try:
            months = int(parts[2])
        except ValueError:
            months = 1

    logger.info(
        f"✅ Payment received: user={user_id}, payload={payload}, "
        f"amount={payment.total_amount} XTR, charge_id={charge_id}, "
        f"type={'subscription' if is_subscription else f'one-time {months}m'}"
    )

    if tier not in TIERS:
        logger.error(f"Unknown tier in payment: {tier}")
        return

    # Calculate expiry based on duration
    now = datetime.now()
    expires = now + timedelta(days=30 * months)

    # Update subscription in DB
    async for session in get_db():
        stmt = select(Subscription).where(Subscription.user_id == user_id)
        sub = (await session.execute(stmt)).scalar_one_or_none()

        if sub:
            sub.tier = tier
            sub.starts_at = now
            sub.expires_at = expires
            sub.is_active = True
            sub.auto_renew = is_subscription
            sub.telegram_payment_charge_id = charge_id if is_subscription else None
            sub.payment_source = PAYMENT_SOURCE_STARS
        else:
            sub = Subscription(
                user_id=user_id,
                tier=tier,
                starts_at=now,
                expires_at=expires,
                is_active=True,
                auto_renew=is_subscription,
                telegram_payment_charge_id=charge_id if is_subscription else None,
                payment_source=PAYMENT_SOURCE_STARS,
            )
            session.add(sub)

        await session.commit()
        break

    # Referral bonuses (Stars payments)
    try:
        await ReferralService.handle_successful_payment(user_id=user_id, tier=tier)
    except Exception as e:
        logger.error(f"[REFERRAL] Failed to handle referral bonuses for Stars payment payload={payload}: {e}", exc_info=True)

    # Send confirmation
    tier_info = TIERS[tier]
    if is_subscription:
        renewal_text = "🔄 Автопродление: ✅ (можно отменить в меню подписок)"
    else:
        dur_label = DURATIONS.get(months, {}).get("label", f"{months} мес")
        renewal_text = f"1️⃣ Разовая оплата на {dur_label} — автопродления нет"

    await message.answer(
        f"🎉 <b>Подписка активирована!</b>\n\n"
        f"Тариф: {tier_info['emoji']} <b>{tier_info['title']}</b>\n"
        f"Действует до: <code>{expires.strftime('%d.%m.%Y')}</code>\n"
        f"{renewal_text}\n\n"
        f"Спасибо за поддержку FoodFlow! 💚",
        parse_mode="HTML",
    )

    logger.info(f"Subscription activated: user={user_id}, tier={tier}, months={months}, expires={expires}, auto_renew={is_subscription}")


# =====================================================
# Cancel Subscription
# =====================================================

@router.callback_query(F.data == "cancel_subscription")
async def handle_cancel_subscription(callback: types.CallbackQuery, bot: Bot):
    """Cancel auto-renewal of the subscription."""
    user_id = callback.from_user.id

    async for session in get_db():
        stmt = select(Subscription).where(Subscription.user_id == user_id)
        sub = (await session.execute(stmt)).scalar_one_or_none()

        if not sub or not sub.is_active or not sub.telegram_payment_charge_id:
            await callback.answer("У вас нет активной платной подписки.", show_alert=True)
            return

        try:
            # Cancel auto-renewal via Telegram API
            await bot.edit_user_star_subscription(
                user_id=user_id,
                telegram_payment_charge_id=sub.telegram_payment_charge_id,
                is_canceled=True,
            )
            sub.auto_renew = False
            await session.commit()

            await callback.answer("Автопродление отключено", show_alert=True)

            builder = InlineKeyboardBuilder()
            builder.button(text="🔙 Назад", callback_data="show_subscriptions")

            await callback.message.edit_text(
                f"🔕 <b>Автопродление отключено</b>\n\n"
                f"Ваша подписка <b>{sub.tier.upper()}</b> продолжит действовать "
                f"до <code>{sub.expires_at.strftime('%d.%m.%Y')}</code>.\n\n"
                f"После этой даты вы перейдёте на бесплатный тариф.",
                parse_mode="HTML",
                reply_markup=builder.as_markup(),
            )
        except Exception as e:
            logger.error(f"Failed to cancel subscription for {user_id}: {e}")
            await callback.answer("❌ Ошибка. Попробуйте позже.", show_alert=True)
        break


# =====================================================
# Mandatory Commands: /paysupport, /terms
# =====================================================

@router.message(Command("paysupport"))
async def paysupport_command(message: types.Message):
    """Mandatory payment support command required by Telegram."""
    builder = InlineKeyboardBuilder()
    builder.button(text="📩 Написать разработчику", callback_data="menu_contact_dev")
    builder.adjust(1)

    await message.answer(
        "💳 <b>Поддержка по платежам</b>\n\n"
        "Если у вас возникли вопросы по оплате, подписке или возврату средств, "
        "нажмите кнопку ниже и опишите проблему. Мы ответим как можно скорее.\n\n"
        "📧 Также вы можете написать на: <code>support@foodflow.app</code>",
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )


@router.message(Command("terms"))
async def terms_command(message: types.Message):
    """Mandatory terms of service command required by Telegram."""
    await message.answer(
        "📜 <b>Условия использования FoodFlow</b>\n\n"
        "1. FoodFlow — бот для трекинга питания, доступный в Telegram.\n\n"
        "2. <b>Подписки:</b> Бот предоставляет бесплатный и платные тарифы. "
        "Платные подписки оплачиваются через Telegram Stars и автоматически "
        "продлеваются каждые 30 дней.\n\n"
        "3. <b>Отмена:</b> Вы можете отменить автопродление в любой момент "
        "через меню подписок. Подписка продолжит действовать до конца "
        "оплаченного периода.\n\n"
        "4. <b>Возвраты:</b> Возврат средств возможен в течение 24 часов "
        "после оплаты. Обратитесь в поддержку (/paysupport).\n\n"
        "5. <b>Данные:</b> Мы не собираем платежные данные пользователей. "
        "Все транзакции обрабатываются Telegram.\n\n"
        "6. <b>Ответственность:</b> Информация о питании предоставляется "
        "в ознакомительных целях и не является медицинской рекомендацией.\n\n"
        "7. Используя FoodFlow, вы соглашаетесь с "
        '<a href="https://telegram.org/tos">Условиями Telegram</a> и '
        '<a href="https://telegram.org/tos/bot-developers">ToS для ботов</a>.\n\n'
        "По всем вопросам: /paysupport",
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
