import logging
import traceback
from aiogram import Router, Bot
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
    update = event.update
    
    error_msg = f"❌ <b>CRITICAL ERROR</b>\n\n"
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
    
    # Optional: Notify user something went wrong (if possible)
    # This is tricky because we don't always have a message to reply to easily in ErrorEvent generic handler without more parsing
    # But usually aiogram logs it.
