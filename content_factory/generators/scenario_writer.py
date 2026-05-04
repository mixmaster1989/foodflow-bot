from __future__ import annotations

import json
import logging
import random

from config import settings
from content_factory.http_client import openrouter_post
from content_factory.situations import SITUATIONS, Situation
from content_factory.state import FactoryState

logger = logging.getLogger(__name__)

MODELS = [
    "google/gemini-3-flash-preview",
    "deepseek/deepseek-v3.2",
    "openai/gpt-5.4-mini",
]

# Фиксированные ситуации — сценарист НЕ должен их повторять
FIXED_SITUATIONS = [s.category for s in SITUATIONS]

FIXED_SCENARIOS = [
    "pain",
    "use_case",
    "anti_old_school",
    "result",
    "myth_buster",
    "lazy_pro",
]

SCENARIO_DESCRIPTIONS = {
    "pain": "боль при ручном подсчёте — человек психует и бросает",
    "use_case": "конкретный сценарий использования: показать как просто",
    "anti_old_school": "высмеять старый способ подсчёта (приложения, таблицы, весы)",
    "result": "через неделю с FoodFlow жизнь изменилась — контроль без напряга",
    "myth_buster": "разбить миф о питании (еда после 18:00, запрещённые продукты и т.д.)",
    "lazy_pro": "ленивый профи: ем всё что хочу, просто контролирую количество",
}


async def generate_scenario(state: FactoryState) -> dict:
    """
    Генерирует свежую ситуацию + сценарий + тему для следующего прогона.
    Смотрит на state чтобы не повторяться.
    Возвращает dict с ключами: situation (Situation), scenario (str), topic (str).
    """
    recent_categories = list(state.last_categories[-12:])
    recent_final_hooks = list(state.last_final_hooks[-3:])
    recent_hooks = list(state.last_hooks[-5:])

    # Какие ситуации уже надоели (были в последних 9 прогонах — весь пул)
    saturated = set(recent_categories[-9:]) if len(recent_categories) >= 9 else set(recent_categories)

    fixed_situations_text = "\n".join(
        f'  - "{s.category}": {s.brief}' for s in SITUATIONS
    )
    fixed_scenarios_text = "\n".join(
        f'  - "{k}": {v}' for k, v in SCENARIO_DESCRIPTIONS.items()
    )

    prompt = f"""Ты — Сценарист контент-завода Telegram-канала FoodFlow.

## ЧТО ТАКОЕ FoodFlow

FoodFlow — Telegram-бот для умного учёта питания. Главная магия: пользователь отправляет фото тарелки, фото чека или голосовое сообщение — и получает КБЖУ (калории, белки, жиры, углеводы) без ручного ввода. Никаких таблиц, весов и приложений с ручным вводом.

Дополнительные возможности:
- Виртуальный холодильник (инвентаризация продуктов)
- AI-рецепты из содержимого холодильника
- Шопинг-мод: сканируешь этикетки в магазине
- Трекинг воды и веса
- Подписки Free/Basic/Pro

## ЦЕЛЕВАЯ АУДИТОРИЯ

Россия, обычные люди (не айтишники): те кто хочет контролировать питание ради похудения, формы или просто осознанности. Без фанатизма, без "грудки с огурцом". Им важно: просто, быстро, без лишних усилий.

## ТВОЯ ЗАДАЧА

Придумать ОДНУ свежую комбинацию для следующего поста:
1. **Ситуацию** — конкретный бытовой момент когда человек что-то ест или думает о еде
2. **Сценарий** — угол подачи материала
3. **Тему** — конкретный заголовок/тезис поста (1-2 предложения)

## ФИКСИРОВАННЫЕ СИТУАЦИИ (уже существуют, можешь РАСШИРЯТЬ но не копировать):
{fixed_situations_text}

## ФИКСИРОВАННЫЕ СЦЕНАРИИ (уже существуют, можешь РАСШИРЯТЬ но не копировать):
{fixed_scenarios_text}

## НЕДАВНО ИСПОЛЬЗОВАННЫЕ СИТУАЦИИ (не повторяй категории из этого списка):
{json.dumps(recent_categories, ensure_ascii=False)}

## НАСЫЩЕННЫЕ КАТЕГОРИИ (были во всех последних прогонах, точно не использовать):
{json.dumps(list(saturated), ensure_ascii=False)}

## ПОСЛЕДНИЕ ФИНАЛЬНЫЕ КРЮЧКИ ПОСТОВ (не повторяй по смыслу):
{json.dumps(recent_final_hooks, ensure_ascii=False)}

## ПОСЛЕДНИЕ ХУКИ (первые строки постов, для разнообразия):
{json.dumps(recent_hooks, ensure_ascii=False)}

## ПРАВИЛА ДЛЯ СИТУАЦИИ

Валидная ситуация = конкретный бытовой момент из жизни, связанный с едой:
- ✅ "офисный обед: корпоратив или столовая, непонятный состав блюд"
- ✅ "перелёт/поезд: еда в дороге, паки снеков и бортовое питание"
- ✅ "детский праздник: торт, конфеты, неловко отказываться"
- ✅ "романтический ужин: хочется не думать о калориях, но тревога есть"
- ✅ "спортзал после тренировки: что съесть чтобы не обнулить результат"
- ✅ "заказ в офис: пицца на всех, непонятно сколько взял"
- ❌ "пошёл в спортзал" — еда не участвует напрямую
- ❌ "принял решение похудеть" — абстракция, не момент еды
- ❌ копия существующих категорий

Ситуация должна быть:
- Конкретной (время/место/что происходит)
- Узнаваемой для российской ЦА
- Связанной с едой или принятием решения о еде

## ПРАВИЛА ДЛЯ СЦЕНАРИЯ

Можешь выбрать один из существующих сценариев ИЛИ придумать новый.
Примеры новых сценариев которые могли бы существовать:
- "social_proof": "другие уже считают — ты ещё нет, отстаёшь"
- "before_after": "было: хаос в голове. стало: ясность за 10 секунд"
- "fear_of_missing": "продолжаешь гадать пока другие знают точно"
- "daily_ritual": "считать КБЖУ как чистить зубы — стало нормой"

## ПРАВИЛА ДЛЯ ТЕМЫ

Тема — это конкретный тезис поста, 1-2 предложения:
- Должна отражать ситуацию + сценарий
- Не абстрактная ("про еду"), а конкретная ("Как не сорваться когда коллеги заказывают пиццу")
- Не рекламный слоган, а жизненная зарисовка

## ВАЖНО

- Не выдумывай новые возможности FoodFlow — только те что описаны выше
- Не используй IT-метафоры (не для айтишников)
- Не обещай результаты (кг/см/сроки)
- Не пиши месяц/год/дату

## ОТВЕТ

Верни СТРОГО JSON без markdown:
{{
  "situation": {{
    "category": "snake_case_название",
    "brief": "краткое описание сцены: где, что происходит, что человек чувствует"
  }},
  "scenario": "название_сценария",
  "scenario_description": "1 предложение: угол подачи",
  "topic": "конкретный тезис поста (1-2 предложения)"
}}
"""

    for model in MODELS:
        try:
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://foodflow.app",
                "X-Title": "FoodFlow Content Factory - Scenario Writer",
            }
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
            }
            data = await openrouter_post(headers=headers, payload=payload, timeout=30.0)
            raw = data["choices"][0]["message"].get("content", "").strip()
            if raw.startswith("```json"):
                raw = raw[7:]
            elif raw.startswith("```"):
                raw = raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            result = json.loads(raw.strip())

            # Валидация
            sit = result.get("situation", {})
            if not sit.get("category") or not sit.get("brief"):
                raise ValueError("Invalid situation in response")
            if not result.get("scenario"):
                raise ValueError("Missing scenario")
            if not result.get("topic"):
                raise ValueError("Missing topic")

            situation = Situation(
                category=sit["category"],
                brief=sit["brief"],
            )
            logger.info(
                f"🎬 Сценарист: ситуация='{situation.category}', "
                f"сценарий='{result['scenario']}', модель={model}"
            )
            return {
                "situation": situation,
                "scenario": result["scenario"],
                "topic": result["topic"],
            }

        except Exception as e:
            logger.warning(f"Scenario writer model {model} failed: {e}")
            continue

    # Fallback: берём случайную из фиксированного пула
    logger.error("❌ Сценарист не ответил — fallback на фиксированный пул")
    from content_factory.situations import pick_situation
    fallback_situation = pick_situation(state, window=10)
    fallback_scenario = random.choice(FIXED_SCENARIOS)
    topics_fallback = {
        "pain": "Срыв с диеты из-за сложности ручного подсчёта",
        "use_case": "Поход в ресторан: КБЖУ за 10 секунд",
        "anti_old_school": "Почему кухонные весы сегодня — это анахронизм",
        "result": "Как контроль питания становится незаметной привычкой",
        "myth_buster": "Разрушение мифа о запрещённых продуктах",
        "lazy_pro": "Гибкая диета: результат без отказа от жизни",
    }
    return {
        "situation": fallback_situation,
        "scenario": fallback_scenario,
        "topic": topics_fallback[fallback_scenario],
    }
