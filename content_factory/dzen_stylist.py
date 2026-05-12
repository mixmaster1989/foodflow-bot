"""
Dzen Stylist: adapts Telegram HTML posts for Yandex Dzen publishing.

Dzen supports limited HTML: <b>, <i>, <a>, <code>, <blockquote>, etc.
Also supports Markdown-like syntax.
"""

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Dzen may use a different model for styling
DZEN_STYLIST_MODEL = "tencent/hy3-preview:free"  # or use OpenRouter free model


@dataclass
class DzenStyleResult:
    ok: bool
    text: str
    issues: list[str]
    model: str = ""


def _convert_html_for_dzen(html: str) -> str:
    """
    Convert Telegram HTML to Dzen-compatible format.
    Dzen supports: <b>, <strong>, <i>, <em>, <a>, <code>, <blockquote>, <br>
    """
    if not html:
        return ""

    t = html

    # Remove unsupported tags but keep content
    # Telegram-specific tags
    t = t.replace("<tg-spoiler>", "").replace("</tg-spoiler>", "")

    # Convert <blockquote> to Dzen-compatible (may use > or <blockquote>)
    t = t.replace("<blockquote>", "\n<blockquote>").replace("</blockquote>", "</blockquote>\n")

    # Ensure <br> or <br/> is used for line breaks
    t = re.sub(r"<br\s*/?>", "<br>", t)

    # Strip any remaining unsupported tags (keep only allowed)
    allowed_tags = r"b|strong|i|em|a|code|blockquote|br|p|div|span"
    t = re.sub(rf"<(?!/?({allowed_tags})).*?>", "", t, flags=re.IGNORECASE)

    # Clean up excessive newlines
    t = re.sub(r"\n{3,}", "\n\n", t).strip()

    return t


async def style_for_dzen(topic: str, text: str) -> DzenStyleResult:
    """
    Style/adapt text for Dzen publishing.

    For now, does simple HTML conversion.
    Can be extended to use AI for better adaptation.
    """
    issues = []

    if not text:
        return DzenStyleResult(ok=False, text="", issues=["Empty input text"])

    try:
        # For now, just convert HTML format
        dzen_text = _convert_html_for_dzen(text)

        if not dzen_text:
            issues.append("Conversion resulted in empty text")
            return DzenStyleResult(ok=False, text=text, issues=issues)

        # Basic validation
        if len(dzen_text) > 50000:
            issues.append("Text exceeds Dzen's size limit (50k chars)")

        return DzenStyleResult(ok=True, text=dzen_text, issues=issues, model="html_converter")

    except Exception as e:
        logger.error(f"Dzen styling failed: {e}")
        return DzenStyleResult(ok=False, text=text, issues=[str(e)])
