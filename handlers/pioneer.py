"""Pioneer Program — inline integration into the main bot.

Allows users who came directly to FoodFlow (bypassing the reception bot)
to earn Pioneer status and bonus PRO days by joining the secret channel.

Flow:
1. After 2nd food log → show one-time Pioneer card
2. User joins channel → check membership → grant +3 days PRO
3. User requests referral link → +1 day PRO (one-time)
4. Each referred friend who joins → +1 day PRO (max 3 friends)
"""
import logging
from datetime import datetime, timedelta

from aiogram import Bot, F, Router, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from database.base import get_db
from database.models import Subscription, User

logger = logging.getLogger(__name__)
router = Router()

# The secret channel ID (same as reception bot)
PIONEER_CHANNEL_ID = -1003856929949
PIONEER_CHANNEL_LINK = "https://t.me/+g1gHtCNUHZBjN2Fi"
MAX_REFERRAL_BONUS = 3  # Max friends that give bonus


@router.callback_query(F.data == "pioneer_claim_info")
async def handle_pioneer_claim_info(callback: types.CallbackQuery) -> None:
    """Show Pioneer program details after user clicks bridge button."""
    await callback.answer()
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📢 Вступить в канал", url=PIONEER_CHANNEL_LINK)
    builder.button(text="✅ Я вступил, проверить!", callback_data="pioneer_check_sub")
    builder.button(text="🏠 В меню", callback_data="main_menu")
    builder.adjust(1)

    text = (
        "🏆 <b>Статус «Пионер» — это ваш вклад в развитие FoodFlow!</b>\n\n"
        "Первые <b>100</b> пользователей получают особые привилегии:\n\n"
        "🎁 <b>+3 дня PRO</b> сразу после вступления\n"
        "🔗 <b>Реферальная ссылка</b> (+1 день за каждого друга)\n"
        "💎 <b>Значок основателя</b> в профиле навсегда\n\n"
        "Чтобы активировать статус, нужно просто вступить в наш закрытый канал для своих 👇"
    )

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())

async def maybe_show_pioneer_offer(user_id: int, bot: Bot, message: types.Message) -> bool:
    """Check if user qualifies for Pioneer offer and show it.
    
    Called after food log is saved. Returns True if offer was shown.
    Triggers on 2nd food log for non-pioneer users.
    """
    async for session in get_db():
        user = await session.get(User, user_id)
        if not user:
            return False

        # Skip if already a pioneer or already offered
        if user.is_pioneer or user.pioneer_offered:
            return False

        # Check food log count
        from sqlalchemy import func

        from database.models import ConsumptionLog
        logs_count = (await session.execute(
            select(func.count()).select_from(ConsumptionLog).where(
                ConsumptionLog.user_id == user_id
            )
        )).scalar() or 0

        # Show Pioneer offer after Guide has been handled (usually 2nd log or later)
        # We trigger it if logs_count >= 2 and it hasn't been offered yet
        if logs_count < 2 or user.pioneer_offered:
            return False

        # Mark as offered so we don't show again
        user.pioneer_offered = True
        await session.commit()
        break

    # Build the Pioneer card
    builder = InlineKeyboardBuilder()
    builder.button(text="📢 Вступить в канал", url=PIONEER_CHANNEL_LINK)
    builder.button(text="✅ Я вступил, проверить!", callback_data="pioneer_check_sub")
    builder.button(text="⏭️ Не сейчас", callback_data="pioneer_dismiss")
    builder.adjust(1)

    text = (
        "🏆 <b>Эй, ты уже освоился! Есть кое-что особенное.</b>\n\n"
        "Первые <b>100</b> пользователей FoodFlow получают\n"
        "статус «<b>Пионер</b>» — это:\n\n"
        "🎁 <b>+3 дня PRO</b> бесплатно\n"
        "🔗 Реферальная ссылка (<b>+1 день</b> за каждого друга)\n"
        "💎 Значок основателя навсегда\n\n"
        "Всего один шаг — вступи в наш закрытый канал 👇"
    )

    await message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
    return True


@router.callback_query(F.data == "pioneer_check_sub")
async def handle_pioneer_check(callback: types.CallbackQuery) -> None:
    """Verify channel membership and grant Pioneer bonuses."""
    user_id = callback.from_user.id
    bot = callback.bot

    # Check if already a pioneer
    async for session in get_db():
        user = await session.get(User, user_id)
        if not user:
            await callback.answer("❌ Ошибка: пользователь не найден.", show_alert=True)
            return
        if user.is_pioneer:
            await callback.answer("✅ Ты уже в списке Пионеров!", show_alert=True)
            return
        break

    # Check channel membership
    try:
        member = await bot.get_chat_member(chat_id=PIONEER_CHANNEL_ID, user_id=user_id)
        if member.status not in ["member", "administrator", "creator"]:
            await callback.answer(
                "❌ Ты ещё не подписан на канал! Подпишись и попробуй снова. 🍏",
                show_alert=True
            )
            return
    except Exception as e:
        logger.error(f"Pioneer channel check error: {e}")
        await callback.answer(
            "⚠️ Ошибка проверки. Убедись, что бот — админ в канале.",
            show_alert=True
        )
        return

    # Grant Pioneer status + bonus days
    async for session in get_db():
        user = await session.get(User, user_id)
        if not user:
            return

        user.is_pioneer = True
        user.is_founding_member = True
        user.pioneer_bonus_days = (user.pioneer_bonus_days or 0) + 3

        # Extend or create subscription
        sub_stmt = select(Subscription).where(Subscription.user_id == user_id)
        sub = (await session.execute(sub_stmt)).scalar_one_or_none()

        now = datetime.now()
        bonus_days = 3

        if sub:
            current_expires = sub.expires_at if sub.expires_at and sub.expires_at > now else now
            sub.expires_at = current_expires + timedelta(days=bonus_days)
            sub.tier = "pro"
            sub.is_active = True
        else:
            sub = Subscription(
                user_id=user_id,
                tier="pro",
                starts_at=now,
                expires_at=now + timedelta(days=bonus_days),
                is_active=True,
                payment_source="pioneer_bonus",
            )
            session.add(sub)

        await session.commit()
        break

    # Show success + referral offer
    builder = InlineKeyboardBuilder()
    builder.button(text="🔗 Получить реф-ссылку (+1 день)", callback_data="pioneer_get_ref")
    builder.adjust(1)

    success_text = (
        "🎯 <b>Поздравляем!</b> Ты в списке Пионеров FoodFlow. 💎\n\n"
        "Тебе начислено <b>+3 дня PRO</b>! 🎁\n\n"
        "Хочешь ещё? Жми кнопку ниже, чтобы получить реф-ссылку.\n"
        "За саму генерацию ссылки дарим <b>+1 день</b>, "
        "а за каждого из первых 3-х друзей — ещё по дню! 🔥"
    )

    try:
        await callback.message.edit_text(
            success_text, parse_mode="HTML", reply_markup=builder.as_markup()
        )
    except Exception:
        await callback.message.answer(
            success_text, parse_mode="HTML", reply_markup=builder.as_markup()
        )
    await callback.answer()


@router.callback_query(F.data == "pioneer_get_ref")
async def handle_pioneer_get_ref(callback: types.CallbackQuery) -> None:
    """Generate referral link and grant +1 day bonus for first request."""
    user_id = callback.from_user.id
    bot = callback.bot

    async for session in get_db():
        user = await session.get(User, user_id)
        if not user:
            await callback.answer("❌ Ошибка.", show_alert=True)
            return

        if not user.is_pioneer:
            await callback.answer("❌ Сначала вступи в канал!", show_alert=True)
            return

        # Grant +1 day for first ref link request
        if not user.pioneer_ref_requested:
            user.pioneer_ref_requested = True
            user.pioneer_bonus_days = (user.pioneer_bonus_days or 0) + 1

            # Extend subscription
            sub_stmt = select(Subscription).where(Subscription.user_id == user_id)
            sub = (await session.execute(sub_stmt)).scalar_one_or_none()
            if sub:
                now = datetime.now()
                current_expires = sub.expires_at if sub.expires_at and sub.expires_at > now else now
                sub.expires_at = current_expires + timedelta(days=1)

            await session.commit()

        current_bonus = user.pioneer_bonus_days or 0
        refs_count = user.pioneer_refs_count or 0
        break

    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=pioneer_{user_id}"

    ref_text = (
        "🚀 <b>Твоя реферальная программа активирована!</b>\n\n"
        f"Твой текущий бонус: <b>{current_bonus} дней PRO</b> 💎\n"
        f"Приглашено друзей: <b>{refs_count}</b> / {MAX_REFERRAL_BONUS}\n\n"
        "Твоя ссылка для друзей:\n"
        f"<code>{ref_link}</code>\n\n"
        "🎁 <b>Условия:</b>\n"
        "• +1 день PRO сразу (уже начислен).\n"
        f"• +1 день за каждого из первых {MAX_REFERRAL_BONUS}-х друзей.\n\n"
        "<i>Делись ссылкой и копи бонусы!</i> 🙌"
    )

    try:
        await callback.message.edit_text(ref_text, parse_mode="HTML")
    except Exception:
        await callback.message.answer(ref_text, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "pioneer_dismiss")
async def handle_pioneer_dismiss(callback: types.CallbackQuery) -> None:
    """User chose 'Not now' — dismiss the card silently."""
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer("Окей! Кнопка «🏆 Стать Пионером» доступна в меню. 😉")


@router.callback_query(F.data == "pioneer_open_offer")
async def handle_pioneer_menu_button(callback: types.CallbackQuery) -> None:
    """Handle the persistent '🏆 Стать Пионером' button from the main menu."""
    user_id = callback.from_user.id

    async for session in get_db():
        user = await session.get(User, user_id)
        if not user:
            await callback.answer("❌ Ошибка.", show_alert=True)
            return

        if user.is_pioneer:
            # Already a pioneer — show status
            bonus = user.pioneer_bonus_days or 0
            refs = user.pioneer_refs_count or 0

            builder = InlineKeyboardBuilder()
            builder.button(text="🔗 Моя реф-ссылка", callback_data="pioneer_get_ref")
            builder.button(text="🔙 Назад", callback_data="main_menu")
            builder.adjust(1)

            text = (
                "🏆 <b>Ты — Пионер FoodFlow!</b> 💎\n\n"
                f"🎁 Бонусов накоплено: <b>{bonus} дней PRO</b>\n"
                f"👥 Приглашено друзей: <b>{refs}</b> / {MAX_REFERRAL_BONUS}\n\n"
                "<i>Продолжай делиться ссылкой, чтобы копить бонусы!</i>"
            )

            await callback.message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
            await callback.answer()
            return
        break

    # Not a pioneer yet — show the offer
    builder = InlineKeyboardBuilder()
    builder.button(text="📢 Вступить в канал", url=PIONEER_CHANNEL_LINK)
    builder.button(text="✅ Я вступил, проверить!", callback_data="pioneer_check_sub")
    builder.button(text="🔙 Назад", callback_data="main_menu")
    builder.adjust(1)

    text = (
        "🏆 <b>Стань Пионером FoodFlow!</b>\n\n"
        "Первые <b>100</b> участников получают:\n\n"
        "🎁 <b>+3 дня PRO</b> бесплатно\n"
        "🔗 Реферальная ссылка (<b>+1 день</b> за каждого друга)\n"
        "💎 Значок основателя навсегда\n\n"
        "Всего один шаг — вступи в наш закрытый канал 👇"
    )

    await callback.message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()


async def process_pioneer_referral(new_user_id: int, referrer_id: int, bot: Bot) -> None:
    """Process pioneer referral when a new user starts the bot via pioneer_XXXX link.
    
    Called from the /start handler when deep link matches 'pioneer_<id>'.
    """
    async for session in get_db():
        referrer = await session.get(User, referrer_id)
        if not referrer or not referrer.is_pioneer:
            return

        refs_count = referrer.pioneer_refs_count or 0
        if refs_count >= MAX_REFERRAL_BONUS:
            return  # Already maxed out

        # Increment referrer's counter + bonus
        referrer.pioneer_refs_count = refs_count + 1
        referrer.pioneer_bonus_days = (referrer.pioneer_bonus_days or 0) + 1

        # Extend referrer's subscription
        sub_stmt = select(Subscription).where(Subscription.user_id == referrer_id)
        sub = (await session.execute(sub_stmt)).scalar_one_or_none()
        if sub:
            now = datetime.now()
            current_expires = sub.expires_at if sub.expires_at and sub.expires_at > now else now
            sub.expires_at = current_expires + timedelta(days=1)

        await session.commit()

        # Notify the referrer
        try:
            await bot.send_message(
                referrer_id,
                "🎉 Твой друг зарегистрировался через твою ссылку!\n"
                "Тебе начислен <b>+1 день PRO</b>! 🚀",
                parse_mode="HTML"
            )
        except Exception:
            pass

        break
