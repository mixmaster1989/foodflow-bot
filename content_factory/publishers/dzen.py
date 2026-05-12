import logging
import re
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)

from config import settings


def _tg_html_to_dzen(text: str) -> str:
    """
    Convert Telegram HTML to Dzen-compatible Markdown/HTML.
    Dzen supports limited HTML: <b>, <i>, <a>, <code>, etc.
    """
    if not text:
        return ""
    t = text
    # Blockquotes: Dzen uses <blockquote> or just plain text with indent
    t = t.replace("<blockquote>", "\n> ").replace("</blockquote>", "\n")
    # Spoilers: Dzen doesn't support, just strip tags
    t = t.replace("<tg-spoiler>", "").replace("</tg-spoiler>", "")
    # Convert <b> to ** for Markdown or keep as <b>
    # Dzen supports <b> and <strong>
    # Strip any remaining unknown tags
    t = re.sub(r"<(?!b|i|a|code|strong|em|br|p|div)[^>]+>", "", t)
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    return t


async def _dzen_api_call(session: aiohttp.ClientSession, method: str, **params: Any) -> Any:
    """
    Call Dzen API.
    Dzen uses Yandex OAuth tokens.
    API endpoint: https://zen.yandex.ru/api/v1/...
    """
    if not settings.DZEN_TOKEN:
        raise RuntimeError("DZEN_TOKEN is not configured")

    headers = {
        "Authorization": f"OAuth {settings.DZEN_TOKEN}",
        "Content-Type": "application/json",
    }

    # Base URL for Dzen API
    base_url = "https://zen.yandex.ru/api/v1"
    url = f"{base_url}/{method}"

    # Add channel_id to params if not present
    if "channel_id" not in params and settings.DZEN_CHANNEL_ID:
        params["channel_id"] = settings.DZEN_CHANNEL_ID

    try:
        r = await session.post(url, headers=headers, json=params, timeout=aiohttp.ClientTimeout(total=60.0))
        r.raise_for_status()
        data = await r.json()
        if "error" in data:
            raise RuntimeError(f"Dzen API error ({method}): {data['error']}")
        return data
    except aiohttp.ClientError as e:
        raise RuntimeError(f"Dzen API request failed ({method}): {e}")


async def publish_to_dzen(text: str, image_url: str | None = None, title: str | None = None) -> bool:
    """
    Publish a post to Yandex Dzen channel.

    Args:
        text: Post text (Telegram HTML format, will be converted)
        image_url: Optional image URL
        title: Optional post title (Dzen posts usually have titles)

    Returns:
        bool: True if published successfully
    """
    if not settings.DZEN_TOKEN or not settings.DZEN_CHANNEL_ID:
        logger.info("Dzen publishing is not configured; skip.")
        return False

    # Convert text to Dzen-compatible format
    dzen_text = _tg_html_to_dzen(text)

    if not dzen_text:
        logger.error("No text to publish to Dzen.")
        return False

    # Extract or generate title
    if not title:
        # Use first line or first 100 chars as title
        lines = [l.strip() for l in dzen_text.split("\n") if l.strip()]
        title = lines[0][:100] if lines else "Новый пост"

    async with aiohttp.ClientSession() as session:
        try:
            # Prepare publication data
            publish_data = {
                "channel_id": settings.DZEN_CHANNEL_ID,
                "title": title,
                "content": dzen_text,
                "is_public": True,
            }

            # TODO: Handle image upload if needed
            # Dzen API may require images to be uploaded first
            if image_url:
                logger.info(f"Image URL provided: {image_url}")
                # Note: Dzen may require separate image upload
                # publish_data["image_url"] = image_url

            # Call Dzen publish API
            result = await _dzen_api_call(session, "publication/create", **publish_data)

            publication_id = result.get("publication_id") or result.get("id")
            logger.info(f"Dzen post published: {publication_id}")
            return True

        except Exception as e:
            logger.error(f"Dzen publish failed: {e}")
            return False
