import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy import select

from database.base import get_db
from database.models import Subscription

logger = logging.getLogger(__name__)

# Development switch: set to True to unlock PRO features for everyone
IS_BETA_TESTING = True

class PaywallMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: dict[str, Any]
    ) -> Any:

        user = event.from_user
        if not user:
            return await handler(event, data)

        tier = "free"

        # Check subscription status
        async for session in get_db():
            stmt = select(Subscription).where(Subscription.user_id == user.id)
            sub = (await session.execute(stmt)).scalar_one_or_none()
            if sub and sub.is_active:
                tier = sub.tier
            break # Just need one session run

        # Global override for beta testing
        if IS_BETA_TESTING:
            tier = "pro"

        data["user_tier"] = tier

        # --- GATEKEEPER LOGIC ---
        # Intercept callbacks
        if isinstance(event, CallbackQuery):
            callback_data = event.data

            # Basic Tier requirements
            basic_features = ["menu_fridge", "menu_recipes"]
            if callback_data in basic_features and tier == "free":
                feature_name = "Умный Холодильник" if "fridge" in callback_data else "Генератор Рецептов"
                await self.show_paywall(event, feature_name, "Basic")
                return

            # Pro Tier requirements
            # (Currently photo AI is via message, handled separately or here if we have a button)

        return await handler(event, data)

    async def show_paywall(self, event: CallbackQuery, feature_name: str, required_tier: str):
        builder = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 Узнать больше о подписках", callback_data="show_subscriptions")]
        ])

        text = (
            f"🔒 <b>Функция недоступна</b>\n\n"
            f"Функция <b>{feature_name}</b> доступна начиная с подписки <b>{required_tier}</b>.\n\n"
            f"Оформите подписку, чтобы разблокировать максимум возможностей из ИИ!"
        )
        await event.answer(text, show_alert=True)
        # Optionally send a new message with the builder
        await event.message.answer(text, parse_mode="HTML", reply_markup=builder)
