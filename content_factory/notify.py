from __future__ import annotations

import logging
from pathlib import Path

from content_factory.publishers.telegram import publish_to_telegram
from config import settings

logger = logging.getLogger(__name__)


async def notify_admin(*, title: str, lines: list[str], run_dir: Path | None = None) -> None:
    if not settings.ADMIN_IDS:
        logger.warning("No ADMIN_IDS configured; skip admin notification.")
        return
    chat_id = settings.ADMIN_IDS[0]
    body = "\n".join([f"<b>{title}</b>"] + [f"- {it}" for it in lines])
    if run_dir:
        body += f"\n\n<code>{run_dir}</code>"
    try:
        await publish_to_telegram(body, target_chat_id=chat_id, parse_mode="HTML")
    except Exception as e:
        logger.warning(f"Admin notify failed: {e}")

