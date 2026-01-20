from aiogram import Bot
from config import settings

class BaseCommandHandler:
    """
    A base class for command handlers that provides common utility methods.
    """

    @staticmethod
    async def send_arbitrary_message(user_id: int, message_text: str):
        """
        Sends a message to a specified user.

        Args:
            user_id: The ID of the user to send the message to.
            message_text: The text of the message to send.
        """
        bot = Bot(token=settings.BOT_TOKEN)
        try:
            await bot.send_message(
                chat_id=user_id,
                text=message_text,
                parse_mode="HTML"
            )
        finally:
            await bot.session.close()

