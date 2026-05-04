from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from content_factory.http_client import openrouter_post

from config import settings

logger = logging.getLogger(__name__)

MODEL = "google/gemini-3-flash-preview"
FALLBACK_MODEL = "deepseek/deepseek-v3.2"

VK_HASHTAGS = [
    "#питание", "#кбжу", "#похудение", "#здоровье", "#контрольпитания",
    "#фудфлоу", "#едаиточка", "#правильноепитание", "#трекингеды",
]


@dataclass(frozen=True)
class VKStyleResult:
    ok: bool
    text: str
    issues: list[str]
    model: str


def _tg_html_to_plain(text: str) -> str:
    """Снимаем TG HTML теги если вдруг текст уже прошёл через TG-стилиста."""
    if not text:
        return ""
    t = text
    t = t.replace("<blockquote>", "").replace("</blockquote>", "")
    t = t.replace("<tg-spoiler>", "").replace("</tg-spoiler>", "")
    t = re.sub(r"<[^>]+>", "", t)
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    return t


async def _call_openrouter_json(*, model: str, prompt: str) -> dict:
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://foodflow.app",
        "X-Title": "FoodFlow Content Factory - VK Stylist",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
    }
    data = await openrouter_post(headers=headers, payload=payload, timeout=35.0)
    raw = (data["choices"][0]["message"].get("content") or "").strip()
    if raw.startswith("```json"):
        raw = raw[7:]
    elif raw.startswith("```"):
        raw = raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    return json.loads(raw.strip())


async def style_for_vk(*, topic: str, text: str) -> VKStyleResult:
    """
    Адаптирует нейтральный текст поста под ВКонтакте.
    Принимает текст после редакции (до или после TG-стилиста — не важно,
    HTML теги будут сняты автоматически).
    """
    clean_text = _tg_html_to_plain(text)

    prompt = f"""Ты — опытный SMM-редактор ВКонтакте. Специализируешься на нише здоровье/питание/похудение.

## ЗАДАЧА

Адаптировать текст поста под публикацию ВКонтакте для сообщества FoodFlow.

FoodFlow — Telegram-бот для учёта питания. Пользователь фотографирует еду или чек и получает КБЖУ без ручного ввода. Аудитория: обычные россияне, которые хотят контролировать питание без фанатизма.

## ИСХОДНЫЙ ТЕКСТ:
\"\"\"{clean_text}\"\"\"

## ТЕМА (контекст): {topic}

## ПРАВИЛА АДАПТАЦИИ ДЛЯ ВК

### Структура поста:
1. **Первая строка — крючок**: останавливает при скролле. Начни с эмодзи + интригующий тезис или вопрос. Максимум 1-2 строки.
2. **Пустая строка** после крючка.
3. **Основной текст**: 2-3 коротких абзаца. Разговорный стиль, как живой человек пишет другу. Между абзацами — пустая строка.
4. **CTA в конце**: вопрос к аудитории ("А у тебя бывало такое?", "Как считаешь?") ИЛИ призыв сохранить ("Сохрани себе 👇"). Это стимулирует алгоритм ВК.
5. **Хэштеги**: 2-3 штуки в самом конце, на отдельной строке. Выбери из релевантных: {", ".join(VK_HASHTAGS[:6])}

### Эмодзи — ОБЯЗАТЕЛЬНО:
- МИНИМУМ 4 эмодзи на весь пост, оптимально 5-6
- Первая строка: 1-2 эмодзи (останавливают скролл)
- Каждый абзац: 1 эмодзи в конце или начале предложения
- CTA строка: 1 эмодзи
- Используй по смыслу: 🍽️🥗🍕🍰🎂📸💡✅➡️👇🔥💪
- НЕ ставить подряд больше 2 штук
- Пост БЕЗ эмодзи — провал, алгоритм ВК не продвигает такой контент

### Стиль:
- Plain text, никакого HTML
- Разговорный, тёплый, без менторства
- Не "корпоративный" — как пишет человек, который сам через это прошёл
- Никакого шейминга и ярлыков
- Гендерно-нейтрально

### Запрещено:
- HTML теги (<b>, <i>, и т.д.) — ВК их не поддерживает в постах
- Даты, месяцы, годы в тексте
- Медицинские обещания и гарантии результатов
- Внутренние названия из кода (UniversalInput и т.п.)
- Хэштег в начале поста
- Более 3 хэштегов
- IT-метафоры (не для айтишной аудитории)
- Слово "КБЖУ" более 1 раза (дальше: "цифры", "данные", "сводка")

### Длина:
- Крючок: 1-2 строки
- Основной текст: 150-400 символов
- Итого с хэштегами: 250-600 символов

## ВАЖНО

Не меняй суть и не добавляй новые факты о FoodFlow.
Сохрани главную мысль исходника, просто упакуй по-вкшному.

## ОТВЕТ

Верни строго JSON без markdown:
{{
  "text": "готовый текст поста для ВК (plain text, с переносами строк через \\n)"
}}
"""

    for model in [MODEL, FALLBACK_MODEL]:
        try:
            res = await _call_openrouter_json(model=model, prompt=prompt)
            vk_text = (res.get("text") or "").strip()
            if not vk_text:
                raise ValueError("Empty text from model")

            # Базовая валидация
            issues = []
            if "<" in vk_text and ">" in vk_text:
                issues.append("html_tags_found")
                # Автоочистка
                vk_text = _tg_html_to_plain(vk_text)
            hashtag_count = len(re.findall(r"#\w+", vk_text))
            if hashtag_count > 3:
                issues.append(f"too_many_hashtags:{hashtag_count}")
            if len(vk_text) > 1000:
                issues.append("too_long")

            logger.info(f"✅ VK Stylist: адаптация готова (модель={model}, символов={len(vk_text)})")
            return VKStyleResult(ok=True, text=vk_text, issues=issues, model=model)

        except Exception as e:
            logger.warning(f"VK stylist model {model} failed: {e}")
            continue

    # Fallback: plain text без адаптации
    logger.error("❌ VK Stylist: все модели упали, fallback на plain text")
    return VKStyleResult(ok=False, text=clean_text, issues=["stylist_failed"], model="fallback")
