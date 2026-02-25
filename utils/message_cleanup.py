"""Module for automatic message cleanup and replacement with main menu.

Contains:
- schedule_message_deletion: Schedule message deletion after timeout and show main menu
"""
import asyncio
import logging
from typing import TYPE_CHECKING

from aiogram import Bot

if TYPE_CHECKING:
    from aiogram.types import Message

logger = logging.getLogger(__name__)

# Timeout in seconds (10 minutes)
MESSAGE_TIMEOUT = 600


async def schedule_message_deletion(
    message: "Message",
    bot: Bot,
    user_name: str = "Пользователь"
) -> None:
    """Schedule message deletion after timeout and replace with main menu.

    After 10 minutes, deletes the message and sends main menu to user.
    Runs in background task, doesn't block execution.

    Args:
        message: Telegram message to delete
        bot: Telegram bot instance
        user_name: User's first name for main menu personalization

    Returns:
        None

    """
    async def _delete_and_show_menu() -> None:
        """Delete message and show main menu after timeout."""
        try:
            await asyncio.sleep(MESSAGE_TIMEOUT)

            # Try to delete the message
            try:
                await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
            except Exception as e:
                logger.warning(f"Failed to delete message {message.message_id}: {e}")

            # Import here to avoid circular imports

            # Send main menu
            try:
                from aiogram.utils.keyboard import InlineKeyboardBuilder

                builder = InlineKeyboardBuilder()
                # Row 1: Shopping Mode (Prominent)
                builder.button(text="🛒 Иду в магазин (AR)", callback_data="start_shopping_mode")
                # Row 2: Core Features
                builder.button(text="📸 Загрузить чек", callback_data="menu_check")
                builder.button(text="🧊 Холодильник", callback_data="menu_fridge")
                builder.button(text="👨‍🍳 Рецепты", callback_data="menu_recipes")
                # Row 3: Additional Features
                builder.button(text="📊 Статистика", callback_data="menu_stats")
                builder.button(text="📝 Список покупок", callback_data="menu_shopping_list")
                # Row 4: Settings & Help
                builder.button(text="⚙️ Настройки", callback_data="menu_settings")
                builder.button(text="ℹ️ Справка", callback_data="menu_help")
                builder.adjust(1, 2, 2, 2)  # Adjust button layout

                await bot.send_message(
                    chat_id=message.chat.id,
                    text=f"👋 Привет, {user_name}!",
                    reply_markup=builder.as_markup()
                )
            except Exception as e:
                logger.error(f"Failed to send main menu after message deletion: {e}")

        except asyncio.CancelledError:
            logger.debug(f"Message deletion task cancelled for message {message.message_id}")
        except Exception as e:
            logger.error(f"Error in message deletion task: {e}")

    # Start background task
    asyncio.create_task(_delete_and_show_menu())

