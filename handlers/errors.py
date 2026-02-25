import logging
import traceback

from aiogram import Bot, Router
from aiogram.types import ErrorEvent

from config import settings

router = Router()
logger = logging.getLogger(__name__)

@router.errors()
async def error_handler(event: ErrorEvent, bot: Bot):
    """Global error handler.

    Catches all errors from updates and forwards traceback to admin.
    """
    exception = event.exception

    error_msg = "❌ <b>CRITICAL ERROR</b>\n\n"
    error_msg += f"<b>Exception:</b> {type(exception).__name__}: {str(exception)}\n\n"

    # limit traceback size
    tb = traceback.format_exc()
    if len(tb) > 3000:
        tb = tb[-3000:]

    error_msg += f"<code>{tb}</code>"

    logger.error(f"Global error caught: {exception}", exc_info=True)

    for admin_id in settings.ADMIN_IDS:
        try:
             await bot.send_message(admin_id, error_msg, parse_mode="HTML")
        except Exception:
            pass

    # Notify user to avoid "eternal spinner" or silence
    try:
        if event.update.callback_query:
            await event.update.callback_query.answer("⚠️ Произошла ошибка. Мы уже чиним!", show_alert=True)
        elif event.update.message:
            await event.update.message.answer("⚠️ <b>Ой! Что-то пошло не так.</b>\nРазработчики уже получили отчет об ошибке.", parse_mode="HTML")
    except Exception:
        # If we can't notify user (e.g. blocked), just ignore
        pass
