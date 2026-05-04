import logging
from aiogram import Bot

from config import settings

logger = logging.getLogger(__name__)

async def publish_to_telegram(
    text: str,
    image_url: str | None = None,
    target_chat_id: int | None = None,
    *,
    parse_mode: str = "HTML",
) -> bool:
    """
    Publish a post to Telegram.
    By default, sends to admin chat for review unless CONTENT_FACTORY_TARGET_CHAT_ID is set.
    """
    token = settings.CONTENT_FACTORY_TELEGRAM_TOKEN or settings.RECEPTION_BOT_TOKEN or settings.BOT_TOKEN
    effective_chat_id = (
        target_chat_id
        or settings.CONTENT_FACTORY_TARGET_CHAT_ID
        or (settings.ADMIN_IDS[0] if settings.ADMIN_IDS else None)
    )

    if not effective_chat_id:
        logger.error("No target chat id configured for Content Factory publishing.")
        return False

    bot = Bot(token=token)
    try:
        logger.info(f"Publishing Content Factory post to chat_id={effective_chat_id}...")
        
        photo = None
        if image_url and image_url != "error" and image_url != "error_no_url":
            if image_url.startswith("data:image"):
                import base64
                from aiogram.types import BufferedInputFile
                try:
                    format, imgstr = image_url.split(';base64,')
                    ext = format.split('/')[-1]
                    image_data = base64.b64decode(imgstr)
                    photo = BufferedInputFile(image_data, filename=f"image.{ext}")
                except Exception as e:
                    logger.warning(f"Base64 decode error: {e}")
                    photo = None
            else:
                photo = image_url

        if photo:
            await bot.send_photo(
                chat_id=effective_chat_id,
                photo=photo,
                caption=text,
                parse_mode=parse_mode,
            )
        else:
            await bot.send_message(
                chat_id=effective_chat_id,
                text=text,
                parse_mode=parse_mode,
            )
        
        logger.info("Post published to Telegram.")
        return True
    except Exception as e:
        logger.error(f"Telegram publish failed: {e}")
        return False
    finally:
        await bot.session.close()
