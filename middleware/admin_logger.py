import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware, Bot
from aiogram.types import TelegramObject, Update

from config import settings

logger = logging.getLogger(__name__)

class AdminLoggerMiddleware(BaseMiddleware):
    def __init__(self, bot: Bot):
        self.bot = bot
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any]
    ) -> Any:

        # Determine event info
        event_info = ""
        user_info = ""
        user_id = 0

        if isinstance(event, Update):
            if event.message:
                user = event.message.from_user
                user_id = user.id
                user_info = f"{user.full_name} (ID: {user.id})"
                event_info = f"Message: {event.message.text}"
            elif event.callback_query:
                user = event.callback_query.from_user
                user_id = user.id
                user_info = f"{user.full_name} (ID: {user.id})"
                event_info = f"Button: {event.callback_query.data}"

        # Don't log admin's own actions to avoid spam loop if admin is testing
        # But user requested "Я должен видеть все нажатия других пользователей"
        if user_id != 0 and user_id not in settings.ADMIN_IDS:
             for admin_id in settings.ADMIN_IDS:
                try:
                    # Log to file as well
                    logger.info(f"Admin Alert: User: {user_info} | Action: {event_info}")

                    await self.bot.send_message(
                        admin_id,
                        f"👀 <b>Log:</b>\nUser: {user_info}\nAction: {event_info}",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass

        return await handler(event, data)
