import asyncio
import json
import logging

from config import settings
from content_factory.http_client import openrouter_post

logger = logging.getLogger(__name__)

# Модели для сценарного отдела
MODELS = [
    "openai/gpt-5.4-mini",
    "google/gemini-3-flash-preview",
]

async def generate_reels_scenario(
    topic: str,
    situation_brief: str,
    *,
    persona_description: str = "Энергичная зожница-прагматик, говорит просто, честно, без пафоса и розовых соплей. Обращается к аудитории как к друзьям.",
    tone_mode: str = "soft"
) -> dict:
    """
    Генерирует детальный сценарий для Reels.
    """
    logger.info(f"🎬 ГЕНЕРАЦИЯ СЦЕНАРИЯ REELS. Тема: '{topic}'")

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://foodflow.app",
        "X-Title": "FoodFlow Content Factory - Reels Generator"
    }

    prompt = f"""
ЗАДАЧА: Написать сценарий для короткого вертикального видео (Instagram Reels/TikTok) про FoodFlow.

О ПРОДУКТЕ:
FoodFlow — бот в Telegram для умного учета калорий. Просто фоткаешь еду/чек или записываешь голос -> получаешь КБЖУ. Без ручного ввода.

ПЕРСОНАЖ (КТО В КАДРЕ):
{persona_description}

ТЕМА ВИДЕО:
"{topic}"

КОНТЕКСТ СИТУАЦИИ:
"{situation_brief}"

СТРУКТУРА СЦЕНАРИЯ:
1. ХУК (0-3 сек): Мощное начало, визуальный или текстовый зацеп.
2. ТЕЛО (3-12 сек): Развертывание проблемы и решение через FoodFlow.
3. ФИНАЛ/CTA (12-15 сек): Призыв к действию (подписка, старт бота).

ТРЕБОВАНИЯ К ТЕКСТУ:
- Живая, разговорная речь. Никаких "уникальных алгоритмов" и "инновационных решений".
- Текст должен быть коротким — человек должен успеть проговорить его за указанное время.
- Используй сленг "своих": "КБЖУ", "дожор", "вписаться в норму", "фотка".

ВЕРНИ ОТВЕТ В JSON:
{{
  "title": "Рабочее название",
  "hook": {{
    "visual": "Что происходит в кадре (движение, мимика)",
    "overlay": "Текст на экране (крупно)",
    "speech": "Что говорит девочка"
  }},
  "body": {{
    "visual": "Действие или нарезка кадров",
    "overlay": "Всплывающие тезисы",
    "speech": "Основной текст"
  }},
  "cta": {{
    "visual": "Финальный жест/эмоция",
    "overlay": "Призыв к действию (например: 'ЕДА в директ')",
    "speech": "Финальная фраза"
  }},
  "music_vibe": "Рекомендация по музыке/звуку"
}}
"""

    for model_name in MODELS:
        for attempt in range(1, 3):
            try:
                payload = {
                    "model": model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "response_format": { "type": "json_object" }
                }

                data = await openrouter_post(headers=headers, payload=payload, timeout=30.0)
                raw_content = data['choices'][0]['message']['content'].strip()

                # Очистка и парсинг
                if raw_content.startswith('```json'): raw_content = raw_content[7:]
                elif raw_content.startswith('```'): raw_content = raw_content[3:]
                if raw_content.endswith('```'): raw_content = raw_content[:-3]

                result = json.loads(raw_content.strip())
                logger.info(f"✅ Сценарий Reels успешно сгенерирован через {model_name}")
                return result
            except Exception as e:
                logger.warning(f"⚠️ Ошибка Reels Generator {model_name} (Attempt {attempt}): {e}")
                await asyncio.sleep(1)
                continue

    return {
        "error": "Не удалось сгенерировать сценарий",
        "title": topic
    }

def format_reels_for_tg(scenario: dict) -> str:
    """
    Форматирует JSON сценария в красивый текст для Telegram.
    """
    if "error" in scenario:
        return f"❌ Ошибка: {scenario['error']}"

    text = f"🎬 <b>СЦЕНАРИЙ REELS: {scenario.get('title', 'Без названия')}</b>\n\n"

    # Хук
    text += "🪝 <b>ХУК (0-3 сек)</b>\n"
    text += f"👀 <i>Визуал:</i> {scenario['hook']['visual']}\n"
    text += f"💬 <i>Речь:</i> «{scenario['hook']['speech']}»\n"
    text += f"📱 <i>Текст на экране:</i> <b>{scenario['hook']['overlay']}</b>\n\n"

    # Суть
    text += "💡 <b>СУТЬ (3-12 сек)</b>\n"
    text += f"🎬 <i>Визуал:</i> {scenario['body']['visual']}\n"
    text += f"💬 <i>Речь:</i> «{scenario['body']['speech']}»\n"
    text += f"📱 <i>Оверлеи:</i> {scenario['body']['overlay']}\n\n"

    # Финал
    text += "🎯 <b>ФИНАЛ / CTA (12-15 сек)</b>\n"
    text += f"😊 <i>Визуал:</i> {scenario['cta']['visual']}\n"
    text += f"💬 <i>Речь:</i> «{scenario['cta']['speech']}»\n"
    text += f"📱 <i>CTA:</i> <b>{scenario['cta']['overlay']}</b>\n\n"

    text += f"🎵 <b>Музыка:</b> {scenario.get('music_vibe', 'На твой вкус')}"

    return text
