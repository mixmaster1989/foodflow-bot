import logging
from datetime import datetime

from aiogram import F, Router, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from database.base import get_db
from database.models import ReferralReward, ReferralEvent, User
from services.referral_service import ReferralService


router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(F.data == "referrals_menu")
async def referrals_menu(callback: types.CallbackQuery) -> None:
    """Show referral cabinet: stats, personal link and list of pending rewards."""
    user_id = callback.from_user.id

    async for session in get_db():
        user = await session.get(User, user_id)

        # Load basic stats
        signup_count = 0
        paid_count = 0
        stmt = select(ReferralEvent).where(ReferralEvent.referrer_id == user_id)
        events = (await session.execute(stmt)).scalars().all()
        for ev in events:
            if ev.event_type == "signup":
                signup_count += 1
            elif ev.event_type == "paid":
                paid_count += 1

        # Pending rewards
        rewards_stmt = select(ReferralReward).where(
            ReferralReward.user_id == user_id,
            ReferralReward.is_active.is_(False),
        )
        pending_rewards = (await session.execute(rewards_stmt)).scalars().all()

        # Active rewards (for info)
        active_stmt = select(ReferralReward).where(
            ReferralReward.user_id == user_id,
            ReferralReward.is_active.is_(True),
        )
        active_rewards = (await session.execute(active_stmt)).scalars().all()

        break

    builder = InlineKeyboardBuilder()

    # Section: personal referral link
    referral_block = ""
    progress_block = ""
    ref_paid_count = 0
    has_month_pro_bonus = False

    if user:
        ref_paid_count = user.ref_paid_count or 0
        # Check if monthly Pro reward exists (pending or active)
        for r in list(pending_rewards) + list(active_rewards):
            if r.reward_type == "pro_days" and r.source == "ref_10_paid":
                has_month_pro_bonus = True
                break

        # Progress to 10 paying users
        left = max(0, 10 - ref_paid_count)
        progress_block = (
            f"🏆 Прогресс до месячного Pro: <b>{min(ref_paid_count, 10)}/10</b> платящих\n"
        )
        if has_month_pro_bonus:
            progress_block += "✅ Бонус 1 месяц Pro уже начислен (см. в бонусах).\n\n"
        else:
            progress_block += f"Приведи ещё <b>{left}</b> платящих — получишь +1 месяц Pro (однократно).\n\n"

        token = user.referral_token
        expires_at = user.referral_token_expires_at

        # Build link text if token exists
        if token:
            # Bot username is stable during bot lifetime, можно получать раз в вызов
            bot_info = await callback.message.bot.get_me()
            bot_username = bot_info.username
            link = f"https://t.me/{bot_username}?start=ref_{token}"

            expired = bool(expires_at and expires_at < datetime.now())
            if expired:
                referral_block = (
                    "🔗 <b>Твоя реферальная ссылка</b>\n"
                    "Срок действия текущей ссылки истёк.\n"
                    "Нажми «🔗 Создать / обновить ссылку», чтобы получить новую.\n\n"
                )
            else:
                exp_text = "Бессрочно"
                if expires_at:
                    exp_text = f"до {expires_at.strftime('%d.%m.%Y %H:%M')} (UTC)"
                referral_block = (
                    "🔗 <b>Твоя реферальная ссылка</b>\n"
                    f"Действует: <b>{exp_text}</b>\n"
                    f"<code>{link}</code>\n\n"
                )
        else:
            referral_block = (
                "🔗 <b>Твоя реферальная ссылка</b>\n"
                "У тебя ещё нет личной ссылки.\n"
                "Нажми кнопку ниже, чтобы создать её и звать друзей.\n\n"
            )

    # Short rules description
    rules_block = (
        "📘 <b>Как работает рефералка</b>\n"
        "• Новый пользователь по ссылке получает <b>3 дня Pro</b> (только для новых).\n"
        "• За каждого, кто оплатил любой тариф — тебе <b>+5 дней Basic</b>.\n"
        "• За <b>10 платящих</b> по твоей ссылке — <b>+1 месяц Pro</b> (единоразово).\n"
        "• Если ты активный куратор — за платящего по кураторской ссылке <b>+5 дней Curator</b>.\n\n"
    )

    # Buttons for link management
    builder.button(text="🔗 Создать / обновить ссылку", callback_data="ref_generate_link")
    builder.button(text="📋 Текст приглашения", callback_data="ref_invite_text")

    # Buttons for pending rewards
    if not pending_rewards:
        rewards_text = "У вас пока нет неактивированных бонусов."
    else:
        rewards_text = "Доступные бонусы:\n\n"
        for r in pending_rewards:
            if r.reward_type == "basic_days":
                label = f"Активировать Basic на {r.days} дн."
            elif r.reward_type == "pro_days":
                label = f"Активировать Pro на {r.days} дн."
            elif r.reward_type == "curator_days":
                label = f"Активировать Curator на {r.days} дн."
            else:
                label = f"Активировать {r.reward_type} ({r.days} дн.)"

            builder.button(
                text=label,
                callback_data=f"ref_reward_activate:{r.id}",
            )

    builder.button(text="🔙 Назад", callback_data="main_menu")
    builder.adjust(1)

    active_summary = ""
    if active_rewards:
        total_basic = sum(r.days for r in active_rewards if r.reward_type == "basic_days")
        total_pro = sum(r.days for r in active_rewards if r.reward_type == "pro_days")
        total_curator = sum(r.days for r in active_rewards if r.reward_type == "curator_days")
        active_summary = (
            "\n\nАктивированные бонусы (суммарно дней):\n"
            f"- Basic: {total_basic}\n"
            f"- Pro: {total_pro}\n"
            f"- Curator: {total_curator}\n"
        )

    text = (
        "🎁 <b>Реферальный кабинет</b>\n\n"
        f"👥 Пришло по ссылкам: <b>{signup_count}</b>\n"
        f"💳 Стали платными: <b>{paid_count}</b>\n"
        f"{progress_block}\n"
        f"{referral_block}"
        f"{rules_block}"
        f"{rewards_text}"
        f"{active_summary}"
    )

    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("ref_reward_activate:"))
async def ref_reward_activate(callback: types.CallbackQuery) -> None:
    """Activate a specific referral reward for current user."""
    user_id = callback.from_user.id
    try:
        reward_id = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.answer("❌ Ошибка параметров награды.", show_alert=True)
        return

    success = await ReferralService.activate_reward(user_id=user_id, reward_id=reward_id)
    if not success:
        await callback.answer("⚠️ Не удалось активировать бонус (проверьте лимит или статус).", show_alert=True)
        return

    await callback.answer("✅ Бонус активирован!", show_alert=True)
    # Refresh menu
    callback.data = "referrals_menu"
    await referrals_menu(callback)


@router.callback_query(F.data == "ref_generate_link")
async def ref_generate_link(callback: types.CallbackQuery) -> None:
    """Generate or refresh personal referral link for regular user."""
    user_id = callback.from_user.id

    # Default: 30 days validity for user links
    result = await ReferralService.generate_referral_token(user_id=user_id, days=30)
    if not result:
        await callback.answer("❌ Не удалось создать ссылку.", show_alert=True)
        return

    token, expires_at = result

    bot_info = await callback.message.bot.get_me()
    bot_username = bot_info.username
    link = f"https://t.me/{bot_username}?start=ref_{token}"

    exp_text = "Бессрочно"
    if expires_at:
        exp_text = f"до {expires_at.strftime('%d.%m.%Y %H:%M')} (UTC)"

    text = (
        "🔗 <b>Твоя новая реферальная ссылка</b>\n\n"
        f"Действует: <b>{exp_text}</b>\n"
        f"<code>{link}</code>\n\n"
        "Отправь этот текст друзьям или используй кнопку «📋 Текст приглашения» в кабинете."
    )

    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer("✅ Ссылка обновлена", show_alert=True)


@router.callback_query(F.data == "ref_invite_text")
async def ref_invite_text(callback: types.CallbackQuery) -> None:
    """Send ready-to-copy invite text with current referral link."""
    user_id = callback.from_user.id

    async for session in get_db():
        user = await session.get(User, user_id)
        break

    if not user:
        await callback.answer("❌ Пользователь не найден.", show_alert=True)
        return

    # Ensure there is a token (create if missing)
    token = user.referral_token
    expires_at = user.referral_token_expires_at
    if not token or (expires_at and expires_at < datetime.now()):
        result = await ReferralService.generate_referral_token(user_id=user_id, days=30)
        if not result:
            await callback.answer("❌ Не удалось подготовить ссылку.", show_alert=True)
            return
        token, expires_at = result

    bot_info = await callback.message.bot.get_me()
    bot_username = bot_info.username
    link = f"https://t.me/{bot_username}?start=ref_{token}"

    invite_text = (
        "Присоединяйся к FoodFlow — бот, который считает калории, рецепты и холодильник за тебя.\n\n"
        "По этой ссылке ты получишь <b>3 дня Pro</b> в подарок (только для новых пользователей):\n"
        f"{link}\n\n"
        "А я получу бонусные дни подписки, если ты оформляешь любой тариф ❤️"
    )

    await callback.message.answer(invite_text, parse_mode="HTML")
    await callback.answer("📋 Текст приглашения отправлен сообщением.", show_alert=True)

