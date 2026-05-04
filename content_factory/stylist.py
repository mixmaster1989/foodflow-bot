from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from content_factory.http_client import openrouter_post

from config import settings

logger = logging.getLogger(__name__)


ALLOWED_TAGS = {
    "b",
    "i",
    "u",
    "s",
    "tg-spoiler",
    "blockquote",
}


@dataclass(frozen=True)
class StyleResult:
    ok: bool
    text_html: str
    issues: list[str]
    model: str


def _find_disallowed_tags(html: str) -> list[str]:
    tags = re.findall(r"</?([a-zA-Z0-9\\-]+)(?:\\s+[^>]*)?>", html)
    bad = sorted({t for t in tags if t not in ALLOWED_TAGS})
    return bad


async def _call_openrouter_json(*, model: str, prompt: str, max_tokens: int, temperature: float) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://foodflow.app",
        "X-Title": "FoodFlow Content Factory - Stylist",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if not model.startswith("x-ai/grok"):
        payload["response_format"] = {"type": "json_object"}
    data = await openrouter_post(headers=headers, payload=payload, timeout=45.0)
    raw_content = data["choices"][0]["message"].get("content")
    if not raw_content:
        raise ValueError("Empty model content")
    raw = str(raw_content).strip()
    if raw.startswith("```json"):
        raw = raw[7:]
    elif raw.startswith("```"):
        raw = raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    return json.loads(raw.strip())


async def decorate_for_telegram(*, topic: str, text: str) -> StyleResult:
    """
    Turn a dry post into a TG-ready post using Telegram HTML formatting.
    Must not change meaning or add facts.
    """
    model = "x-ai/grok-4.1-fast"
    prompt = f"""
ЦЕЛЕВАЯ АУДИТОРИЯ (ЦА):
- РФ, обычные люди (не айтишники). Оформление — простое, “телеграмное”, без снобизма.

ЗАПРЕЩЕНО (пример и почему):
- Плохо: «…как писать код в блокноте» — IT-метафора, не для ЦА. Если такое есть в тексте — НЕ выделяй жирным и не усиливай, лучше переформулируй нейтрально, не меняя смысла.

Ты — редактор Telegram-канала FoodFlow (РФ аудитория). Твоя задача: УПАКОВАТЬ текст как пост топового канала.
Ты НЕ перепридумываешь смысл. Ты НЕ добавляешь новые факты/фичи/обещания. Только оформление и улучшение читабельности.

Telegram поддерживает ТОЛЬКО эти HTML-теги (никаких других):
<b>жирный</b>, <i>курсив</i>, <u>подчёркнутый</u>, <s>зачёркнутый</s>,
<tg-spoiler>скрытый текст</tg-spoiler>, <blockquote>цитата</blockquote>, <blockquote expandable>длинная цитата</blockquote>

ПРАВИЛА ФОРМАТИРОВАНИЯ:
1) Абзацы: разделяй через \\n\\n.
2) Заголовок: первое предложение оформи в <b></b> и добавь рядом 2–3 уместных эмодзи.
3) Выделение: 1–2 инсайта на абзац выделяй <b></b>. Интригу — в <tg-spoiler></tg-spoiler>.
4) Эмодзи: максимум 3 эмодзи на весь пост. Не ставь подряд больше 2.
5) Финал: последнее предложение оберни в <blockquote></blockquote>.
   - финал должен быть жёстким и коротким (до 10 слов), формата выбор/давление (либо/либо, или/или).
   - запрещено завершать ватно («остальное…», «не переживай…», «бот возьмёт…»).
6) Запрещено: даты/годы/месяцы ("апрель 2026", "в 2026"), внутренние названия из кода, английские артефакты.
7) Тон: живой, телеграмный, но без оскорблений и без шейминга.

ТЕМА (контекст, не вставляй как заголовок дословно): {topic}

ИСХОДНЫЙ ТЕКСТ:
\"\"\"{text}\"\"\"

Верни ТОЛЬКО валидный JSON:
{{
  "text_html": "..."
}}
""".strip()

    try:
        res = await _call_openrouter_json(model=model, prompt=prompt, max_tokens=5000, temperature=0.3)
        text_html = (res.get("text_html") or "").strip()
        issues: list[str] = []
        if not text_html:
            issues.append("empty_output")
        bad_tags = _find_disallowed_tags(text_html)
        if bad_tags:
            issues.append(f"disallowed_tags:{bad_tags}")
        if issues:
            return StyleResult(ok=False, text_html=text_html or text, issues=issues, model=model)
        return StyleResult(ok=True, text_html=text_html, issues=[], model=model)
    except Exception as e:
        logger.warning(f"Stylist failed: {e}")
        return StyleResult(ok=False, text_html=text, issues=["stylist_failed"], model=model)

