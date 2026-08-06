import os
import sys
import json
import logging
import base64
import re
from pathlib import Path
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import aiohttp

# Add root directory to path for config imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings
from content_factory.http_client import openrouter_post
from content_factory.generators.image import generate_image

logger = logging.getLogger("content_factory.autonomous_shorts")
MOSCOW_TZ = ZoneInfo("Europe/Moscow")
B2B_SHORTS_WEEKDAY = 6  # Sunday MSK — 1 B2B short per week

def is_b2b_shorts_slot() -> bool:
    return datetime.now(MOSCOW_TZ).weekday() == B2B_SHORTS_WEEKDAY


LLM_MODELS = [
    "qwen/qwen3.8-max",
    "google/gemini-3.5-flash-lite",
    "openai/gpt-4o-mini",
    "deepseek/deepseek-v4-pro"
]

SYSTEM_PROMPT = """Ты — опытный ИИ-сценарист и маркетолог для проекта FoodFlow (@FoodFlow2026bot).
Твоя цель — придумать вирусную тему, текст и промпт для утреннего Shorts-ролика, который бьет по САМЫМ ОСТРЫМ И ВЫСОКОКОНВЕРСИОННЫМ БОЛЯМ целевой аудитории.

## ПРИОРИТЕТНЫЕ ВИРУСНЫЕ НАПРАВЛЕНИЯ ТЕМ (БЕРИ ИДЕИ ИЗ ЭТИХ КАТЕГОРИЙ):
1. **Сладкое и запреты:** Почему жесткий запрет на шоколад/торт/выпечку гарантированно ведет к срыву и как съесть сладость без чувства вины.
2. **Вечерний дожор:** Стояла в 11 вечера у открытого холодильника, срыв после рабочего дня, эмоциональное заедание усталости.
3. **Вещи из шкафа малы:** Влезть в любимые джинсы, весы после выходных (+1.5 кг задержки воды), страх не угадать калории на глаз.
4. **Офисные перекусы и контейнеры:** Ночные чаепития на работе, перекус печеньем от скуки.

## ЧТО ТАКОЕ FoodFlow И ЕГО ФИЧИ:
FoodFlow — умная экосистема и Telegram-бот для контроля питания. Основные фичи:
1. Учет по фото и голосу: фото тарелки или голосовое — КБЖУ за 3 секунды.
2. AI-рецепты по фото холодильника.
3. Шопинг-мод: сканирование этикеток.
4. Трекинг веса и воды.

## ЦЕЛЕВАЯ АУДИТОРИЯ
Обычные люди, которые хотят контролировать вес без фанатизма, жестких диет и чувства вины.

## ЗОЛОТАЯ СТРУКТУРА ТЕКСТА SHORTS (200-300 символов, СТРОГО НЕ БОЛЬШЕ 300):
1. **Хук** — конкретная жизненная ситуация, НЕ вопрос. Примеры хороших хуков: «Вчера в 11 вечера стояла у холодильника и ненавидела себя.», «Подруга скинула фото торта — и я сорвалась.», «Достала любимые джинсы из шкафа, а они не застегнулись.»
2. **Простое объяснение** — 1-2 предложения по максимум 15 слов каждое.
3. **Нативная интеграция FoodFlow** — мягко, одним предложением, если уместно.
4. **Loop-финал** — последнее предложение должно быть коротким неожиданным утверждением или вопросом, чтобы зритель хотел пересмотреть ролик. НЕ проси лайк, НЕ проси комментарий, НЕ проси подписку — это будет в описании видео.

⚠️ СТОП-СЛОВА (ЗАПРЕЩЕНО ИСПОЛЬЗОВАТЬ): кортизол, грелин, лептин, дофамин, серотонин, метаболизм, гормон, нейромедиатор, инсулиновый. Пиши простым языком, как подруге за чаем.

ВЕРНИ СТРОГО JSON-ОБЪЕКТ СЛЕДУЮЩЕГО ФОРМАТА (БЕЗ ДРУГОГО ТЕКСТА И БЕЗ MARKDOWN ```json):
{
  "topic": "Привлекательное название темы ролика (до 60 символов)",
  "text": "Готовый сценарий для озвучки 200-300 символов. Пиши от первого лица (диетолог Лена/Анна), заботливым тоном. Упоминай FoodFlow (@FoodFlow2026bot).",
  "image_prompt": "Промпт на английском для генерации стильной картинки (photorealistic, 8k, вертикальный кадр --ar 4:5). Без текста и вотермарок."
}
"""

SYSTEM_PROMPT_ES = """Eres un guionista y especialista en marketing de IA experto para el proyecto FoodFlow (@FoodFlow2026bot).
Tu objetivo es idear un tema viral, guión y prompt de imagen para un video de Shorts matutino adaptado a la audiencia hispanohablante (Latinoamérica y España).
El contenido debe enfocarse en los dolores de la alimentación emocional, el sobrepeso, el miedo a las calorías y la ansiedad por las dietas restrictivas.

## QUÉ ES FoodFlow Y SUS CARACTERÍSTICAS:
FoodFlow es un bot de Telegram para controlar la nutrición:
1. Registro por foto y voz: foto del plato o mensaje de voz → calorías y macros en 3 segundos.
2. Recetas de IA por foto de refrigerador.
3. Modo de compras: escaneo de etiquetas.
4. Seguimiento de peso y agua sin estrés.

## AUDIENCIA OBJETIVO
Personas comunes que quieren controlar su peso sin obsesionarse con básculas ni dietas estrictas.

## DIRECTRICES CULTURALES (MUY IMPORTANTE):
- Los prompts visuales DEBEN reflejar la cultura alimentaria de España y Latinoamérica (tacos, aguacate, arepas, empanadas, tortillas, jugos tropicales).
- Absolutamente nada de comida rusa/del este de Europa y ningún texto en cirílico.

## ESTRUCTURA DE TEXTO DE SHORTS (200-300 caracteres, ESTRICTAMENTE NO MÁS DE 300):
1. **Gancho** — situación concreta de la vida real, NO una pregunta. Buenos ejemplos: "Anoche a las 11 estaba frente al refrigerador odiándome.", "Mi amiga me mandó foto de un pastel y perdí el control." Malos ejemplos: "¿Te ha pasado que...?", "¿Alguna vez te preguntaste...?"
2. **Explicación simple** — 1-2 frases de máximo 15 palabras cada una.
3. **Integración nativa de FoodFlow** — una sola frase, solo si es natural.
4. **Final Loop** — la última frase debe ser una afirmación inesperada o pregunta corta que motive a re-ver el video. NO pidas like, NO pidas comentario, NO pidas suscripción — eso va en la descripción del video.

⚠️ PALABRAS PROHIBIDAS: cortisol, grelina, leptina, dopamina, serotonina, metabolismo, hormona, neurotransmisor, insulínico. Escribe en lenguaje simple, como hablando con una amiga.

DEVUELVE ÚNICAMENTE UN OBJETO JSON CON EL SIGUIENTE FORMATO (SIN TEXTO ADICIONAL Y SIN CÓDIGO MARKDOWN ```json):
{
  "topic": "Título atractivo y viral del tema (hasta 60 caracteres)",
  "text": "Guión de 200-300 caracteres. Primera persona (nutricionista empática), tono amigable. Menciona FoodFlow (@FoodFlow2026bot).",
  "image_prompt": "Prompt en inglés para imagen (photorealistic, 8k, vertical --ar 4:5). Sin texto ni marcas de agua."
}
"""

B2B_SYSTEM_PROMPT = """Ты — опытный ИИ-сценарист B2B-маркетинга для FoodFlow (@FoodFlow2026bot).
Твоя цель — короткий YouTube Shorts для АУДИТОРИИ ПРОФЕССИОНАЛОВ: нутрициологов, диетологов, фитнес-тренеров и кураторов марафонов похудения.

## ПРОДУКТ ДЛЯ B2B (Кабинет куратора FoodFlow)
- Клиенты фотографируют еду / надиктовывают — ИИ считает КБЖУ без ручного ввода.
- Куратор видит сводку по всем подопечным в Telegram: кто заполнил день, кто молчит.
- Марафоны с участниками, реферальные ссылки, рассылки подопечным.
- Демо куратора: 7 дней бесплатно (без карты).

## БОЛИ КУРАТОРА (бей в них)
- Ручная проверка фотоотчётов и тарелок в чате на 15–30 человек.
- Усталость от Excel, FatSecret и «забыла записать» у клиентов.
- Низкая доходимость марафона из-за рутины.

## СТРУКТУРА ТЕКСТА (300–450 символов)
1. Хук: «Ведёшь марафон / клиентов по питанию?»
2. Боль: рутина проверки отчётов, глаза замыливаются.
3. Решение: кабинет куратора FoodFlow — клиент фоткает, ты видишь аналитику.
4. CTA: «Пиши в комментариях, сколько у тебя подопечных — расскажу, как подключить демо!»

НЕ упоминай в тексте прямую ссылку t.me — только FoodFlow и @FoodFlow2026bot
"""

def get_active_series_context(locale: str, runs_dir: str | Path = "/home/user1/foodflow-bot_new/content_factory/runs") -> dict | None:
    """
    Checks the runs directory to find if the last B2C video was part of a series
    and if that series is still active (part < total_parts).
    """
    path = Path(runs_dir)
    if not path.exists():
        return None
    
    dirs = [d for d in path.iterdir() if d.is_dir() and "autonomous_morning_shorts" in d.name]
    dirs.sort(key=lambda d: d.name, reverse=True)
    
    for d in dirs:
        post_json = d / "post.json"
        if post_json.exists():
            try:
                with open(post_json, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("locale", "ru") == locale:
                        # Skip B2B runs when searching for B2C series
                        if data.get("audience") == "b2b_curator":
                            continue
                        series = data.get("series")
                        if series:
                            part = series.get("part", 1)
                            total_parts = series.get("total_parts", 3)
                            if part < total_parts:
                                return series
                            else:
                                return None
                        # If the most recent B2C post has no series, we assume no series is active
                        return None
            except Exception:
                continue
    return None


def get_recent_morning_shorts_topics(
    locale: str = "ru",
    b2b: bool = False,
    runs_dir: str | Path = "/home/user1/foodflow-bot_new/content_factory/runs",
    limit: int = 7,
) -> list[str]:
    """
    Scans the runs directory and returns the topics of the most recent morning Shorts
    for the given locale/audience type to prevent topic duplication in new generations.
    """
    path = Path(runs_dir)
    if not path.exists():
        return []

    dirs = [d for d in path.iterdir() if d.is_dir() and "T" in d.name and d.name[0].isdigit()]
    dirs.sort(key=lambda d: d.name, reverse=True)

    topics: list[str] = []
    for d in dirs:
        if len(topics) >= limit:
            break
        post_json = d / "post.json"
        if not post_json.exists():
            continue
        try:
            with open(post_json, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Match locale
            if data.get("locale", "ru") != locale:
                continue
            # Match audience type
            is_b2b_run = data.get("audience") == "b2b_curator"
            if b2b != is_b2b_run:
                continue
            topic = data.get("topic", "").strip()
            if topic:
                topics.append(topic)
        except Exception:
            continue

    return topics


def get_recent_morning_shorts_texts(
    locale: str = "ru",
    b2b: bool = False,
    runs_dir: str | Path = "/home/user1/foodflow-bot_new/content_factory/runs",
    limit: int = 20,
) -> list[str]:
    """Scans the runs directory and returns script texts of recent posts for Jaccard deduplication."""
    path = Path(runs_dir)
    if not path.exists():
        return []

    dirs = [d for d in path.iterdir() if d.is_dir() and "T" in d.name and d.name[0].isdigit()]
    dirs.sort(key=lambda d: d.name, reverse=True)

    texts: list[str] = []
    for d in dirs:
        if len(texts) >= limit:
            break
        post_json = d / "post.json"
        if not post_json.exists():
            continue
        try:
            with open(post_json, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("locale", "ru") != locale:
                continue
            is_b2b_run = data.get("audience") == "b2b_curator"
            if b2b != is_b2b_run:
                continue
            text = data.get("text", "").strip()
            if text:
                texts.append(text)
        except Exception:
            continue
    return texts


def get_jaccard_similarity(text1: str, text2: str) -> float:
    """Calculates Jaccard similarity score between two texts based on word tokens."""
    words1 = set(re.findall(r"\w+", text1.lower()))
    words2 = set(re.findall(r"\w+", text2.lower()))
    if not words1 or not words2:
        return 0.0
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    return len(intersection) / len(union)


async def generate_shorts_basis(*, b2b: bool = False, locale: str = "ru") -> dict:
    """
    Calls OpenRouter to generate topic, scenario text, and image prompt for the morning Shorts.
    Supports locale='ru' (Russian) and locale='es' (Spanish/LATAM).
    Prevents topic duplication by passing recently used topics as excluded in the prompt.
    Organizes B2C videos into 3-4 part series (serials) to increase retention.
    """
    active_series = None
    if not b2b:
        active_series = get_active_series_context(locale=locale)

    if locale == "es":
        kind = "B2C ES/LATAM"
        system_prompt = SYSTEM_PROMPT_ES
    elif b2b:
        kind = "B2B-кураторский"
        system_prompt = B2B_SYSTEM_PROMPT
    else:
        kind = "B2C RU"
        system_prompt = SYSTEM_PROMPT
        
    # Append Series instructions if B2C
    if not b2b:
        if active_series:
            current_part = active_series["part"] + 1
            total_parts = active_series["total_parts"]
            series_name = active_series["name"]
            today_topic = active_series["next_part_topic"]
            prev_hook = active_series.get("next_part_hook", "")
            full_plan = active_series.get("full_plan", [])
            
            # Find the topic for the next episode if any
            next_part_topic = ""
            if current_part < total_parts:
                for p in full_plan:
                    if p.get("part") == current_part + 1:
                        next_part_topic = p.get("topic", "")
                        break
            
            if locale == "es":
                series_instruction = f"""

⚠️ EPISODIO DE SERIE EN CURSO (Parte {current_part} de {total_parts}):
Tema OBLIGATORIO de hoy: "{today_topic}"
NO menciones en el guión que es una serie, ni el número de episodio, ni hagas recap del anterior. Solo escribe sobre el tema obligatorio.
El texto debe tener 200-300 caracteres, con la misma estructura (gancho situacional + explicación + FoodFlow + loop-final).

DEVUELVE ÚNICAMENTE UN OBJETO JSON (SIN TEXTO ADICIONAL Y SIN CÓDIGO MARKDOWN ```json):
{{
  "topic": "{today_topic}",
  "text": "...",
  "image_prompt": "...",
  "next_part_hook": "Un gancho intrigante sobre: {next_part_topic}"
}}
"""
            else:
                series_instruction = f"""

⚠️ ПРОДОЛЖЕНИЕ СЕРИАЛА (Серия {current_part} из {total_parts}):
Обязательная тема сегодня: «{today_topic}»
НЕ озвучивай в тексте номер серии, название цикла и рекап прошлой серии. Просто пиши о теме дня.
Текст 200-300 символов, по той же структуре (хук-ситуация + объяснение + FoodFlow + loop-финал).

ВЕРНИ СТРОГО JSON-ОБЪЕКТ (БЕЗ ДРУГОГО ТЕКСТА И БЕЗ MARKDOWN ```json):
{{
  "topic": "{today_topic}",
  "text": "...",
  "image_prompt": "...",
  "next_part_hook": "Интригующий крючок про: {next_part_topic}"
}}
"""
            # Replace the standard format instructions at the end of the system prompt
            system_prompt = system_prompt.replace(
                "ВЕРНИ СТРОГО JSON-ОБЪЕКТ СЛЕДУЮЩЕГО ФОРМАТА (БЕЗ ДРУГОГО ТЕКСТА И БЕЗ MARKDOWN ```json):", ""
            ).replace(
                "DEVUELVE ÚNICAMENTE UN OBJETO JSON CON EL SIGUIENTE FORMATO (SIN TEXTO ADICIONAL Y SIN CÓDIGO MARKDOWN ```json):", ""
            )
            system_prompt += series_instruction
        else:
            # Start a new series
            if locale == "es":
                series_instruction = """

⚠️ NUEVA SERIE DE SHORTS (3 EPISODIOS):
Elige un tema general interesante sobre nutrición o mitos alimentarios.
Planifica 3 episodios. Escribe el guión para el Episodio 1 hoy.
NO menciones en el guión que es una serie ni el número de episodio. Solo escribe un Shorts normal sobre el tema.

DEVUELVE ÚNICAMENTE UN OBJETO JSON (SIN TEXTO ADICIONAL Y SIN CÓDIGO MARKDOWN ```json):
{
  "topic": "Tema del primer episodio",
  "text": "Guión de 200-300 caracteres (gancho situacional + explicación + FoodFlow + loop-final). NO menciones la serie.",
  "image_prompt": "Prompt de imagen",
  "series": {
    "name": "Nombre de la serie (atractivo)",
    "part": 1,
    "total_parts": 3,
    "next_part_topic": "Tema del episodio 2",
    "next_part_hook": "Un gancho intrigante para el episodio 2",
    "full_plan": [
      {"part": 1, "topic": "Tema del episodio 1"},
      {"part": 2, "topic": "Tema del episodio 2"},
      {"part": 3, "topic": "Tema del episodio 3"}
    ]
  }
}
"""
            else:
                series_instruction = """

⚠️ ЗАПУСК НОВОГО МИНИ-СЕРИАЛА (3 СЕРИИ):
Выбери общую тему (например: «Ловушки пищевых привычек», «Почему мы переедаем», «Страхи перед едой»).
Распланируй 3 серии. Сегодня напиши сценарий для Серии 1.
НЕ озвучивай в тексте, что это серия или цикл. Просто пиши обычный Shorts на тему первой серии.

ВЕРНИ СТРОГО JSON-ОБЪЕКТ (БЕЗ ДРУГОГО ТЕКСТА И БЕЗ MARKDOWN ```json):
{
  "topic": "Тема первой серии",
  "text": "Текст 200-300 символов (хук-ситуация + объяснение + FoodFlow + loop-финал). НЕ упоминай серию.",
  "image_prompt": "Промпт картинки",
  "series": {
    "name": "Название сериала (цепляющее)",
    "part": 1,
    "total_parts": 3,
    "next_part_topic": "Тема второй серии",
    "next_part_hook": "Интригующий крючок для второй серии",
    "full_plan": [
      {"part": 1, "topic": "Тема первой серии"},
      {"part": 2, "topic": "Тема второй серии"},
      {"part": 3, "topic": "Тема третьей серии"}
    ]
  }
}
"""
            # Clean standard JSON format strings
            system_prompt = system_prompt.replace(
                "ВЕРНИ СТРОГО JSON-ОБЪЕКТ СЛЕДУЮЩЕГО ФОРМАТА (БЕЗ ДРУГОГО ТЕКСТА И БЕЗ MARKDOWN ```json):", ""
            ).replace(
                "DEVUELVE ÚNICAMENTE UN OBJETO JSON CON EL SIGUIENTE FORMATO (SIN TEXTO ADICIONAL Y SIN CÓDIGO MARKDOWN ```json):", ""
            )
            system_prompt += series_instruction

    # Add Day-of-Week Archetype matrix for B2C RU
    if locale == "ru" and not b2b and not active_series:
        weekday_idx = datetime.now(MOSCOW_TZ).weekday()
        DAY_OF_WEEK_ARCHETYPES = {
            0: ("Синдром отёков & Весы после выходных", "Сфокусируйся на задержке воды после выходных (+1.5 кг на весах в понедельник — это отёки и соленое, а не жир). Хук про незастёгивающиеся джинсы или удивление цифре на весах."),
            1: ("Сладкое & Снятие пищевых табу", "Сфокусируйся на теме снятия жестких запретов на шоколад/торты/выпечку. Хук про 3 эклера в машине или шоколадный батончик из заначки без чувства вины."),
            2: ("Реальная история клиента / Кейс", "Сфокусируйся на формате мини-истории клиента (Марина/Катя/Анна). Хук про человека, который 3 года считал калории на глаз и сорвался из-за контейнеров."),
            3: ("Офисный дожор в 15:00 & Скука", "Сфокусируйся на теме дневного/офисного дожора от рутины и скуки в 15:00. Хук про печенье на ресепшн или сушки за рабочим столом."),
            4: ("Пятничный вечер, Застолье & Бар", "Сфокусируйся на теме пятничного отдыха с друзьями (бар/ресторан/пицца). Хук про страх перечеркнуть неделю одним ужином в пятницу."),
            5: ("Ночной холодильник в 23:00", "Сфокусируйся на теме ночного дожора в 23:00 после тяжёлой недели. Хук про тихий свет открытого холодильника в темноте и съеденный сырок."),
            6: ("B2B Кураторы & Нутрициология", "Экспертный B2B разбор для нутрициологов и фитнес-тренеров.")
        }
        arch_title, arch_desc = DAY_OF_WEEK_ARCHETYPES.get(weekday_idx, DAY_OF_WEEK_ARCHETYPES[0])
        system_prompt += f"\n\n🎯 ДНЕВНОЙ РАКУРС И АРХЕТИП ДНЯ ({arch_title}):\n{arch_desc}\nОбязательно добавь 1 яркую конкретную мелкую бытовую деталь (напр. '3 эклера в машине', 'сушки на кухонном столе', 'любимая юбка').\n"

    # Prevent topic & text duplication
    recent_topics = get_recent_morning_shorts_topics(locale=locale, b2b=b2b)
    recent_texts = get_recent_morning_shorts_texts(locale=locale, b2b=b2b, limit=20)

    if recent_topics:
        formatted_topics = "\n".join(f"- {t}" for t in recent_topics)
        if locale == "es":
            exclusion_instruction = (
                f"\n\n⚠️ IMPORTANTE: EVITA LOS SIGUIENTES TEMAS RECIENTES (YA PUBLICADOS):\n"
                f"{formatted_topics}\n"
                f"Debes proponer un tema COMPLETAMENTE NUEVO y diferente. "
                f"Por ejemplo: mitos sobre el agua, comer por aburrimiento, por qué el peso fluctúa repentinamente, "
                f"la verdad sobre los carbohidratos en la noche, el alcohol y las calorías, etc. "
                f"¡NO repitas el tema de prohibiciones, restricciones de comida o culpa por comer chocolate!"
            )
        else:
            exclusion_instruction = (
                f"\n\n⚠️ ВАЖНО: ИСКЛЮЧИ СЛЕДУЮЩИЕ ТЕМЫ (ОНИ УЖЕ ОПУБЛИКОВАНЫ):\n"
                f"{formatted_topics}\n"
                f"Не повторяй в точности эти уже сделанные темы. "
                f"Создавай новые острые жизненные ситуации про сладкое без чувства вины, вечерние дожоры, весы после выходных или одежду из шкафа!"
            )
        system_prompt += exclusion_instruction

    logger.info(f"🧠 Генерация основы для автономного утреннего Shorts ({kind})...")
    
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://foodflow.app",
        "X-Title": "FoodFlow Content Factory - Morning Shorts Generator",
    }
    
    for model in LLM_MODELS:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": system_prompt}],
            "response_format": {"type": "json_object"},
            "temperature": 0.8,
        }
        try:
            data = await openrouter_post(headers=headers, payload=payload, timeout=60.0)
            raw = data["choices"][0]["message"].get("content", "").strip()
            
            # Clean markdown formatting if present
            if raw.startswith("```json"):
                raw = raw[7:]
            elif raw.startswith("```"):
                raw = raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
                
            res = json.loads(raw.strip())
            
            # Simple validation
            if not res.get("topic") or not res.get("text") or not res.get("image_prompt"):
                raise ValueError("Missing required fields in generated Shorts basis.")

            # Jaccard similarity duplicate guard
            if recent_texts:
                for past_t in recent_texts:
                    sim = get_jaccard_similarity(res["text"], past_t)
                    if sim > 0.55:
                        logger.warning(f"⚠️ Семантический дубликат ({sim*100:.1f}% сходство): '{res['topic']}'. Перегенерируем...")
                        raise ValueError(f"High text similarity ({sim*100:.1f}%) with recent post.")
                
            # Series integration
            if not b2b:
                if active_series:
                    res["series"] = {
                        "name": series_name,
                        "part": current_part,
                        "total_parts": total_parts,
                        "next_part_topic": next_part_topic,
                        "next_part_hook": res.get("next_part_hook", f"В следующей части мы продолжим тему '{series_name}'"),
                        "full_plan": full_plan
                    }
                else:
                    if not res.get("series") or not isinstance(res["series"], dict):
                        res["series"] = {
                            "name": res.get("topic", "Секреты питания"),
                            "part": 1,
                            "total_parts": 3,
                            "next_part_topic": "Как гормоны мешают сбросить вес",
                            "next_part_hook": "В следующей серии мы разберем, как гормоны мешают сбросить вес и что с этим делать.",
                            "full_plan": [
                                {"part": 1, "topic": res.get("topic", "Секреты питания")},
                                {"part": 2, "topic": "Как гормоны мешают сбросить вес"},
                                {"part": 3, "topic": "Простые привычки для сытости"}
                            ]
                        }
                
            logger.info(f"✅ Основа успешно сгенерирована с использованием модели: {model}")
            return res
        except Exception as e:
            logger.warning(f"⚠️ Модель {model} при генерации основы Shorts выдала ошибку: {e}")
            continue
            
    logger.error("❌ Все модели генерации основы Shorts упали! Используем fallback.")
    if locale == "es":
        return {
            "topic": "Cómo ganarle a la culpa por los antojos por estrés",
            "text": "¿Otra vez buscando chocolate por estrés en el trabajo? Deja de culparte. Tu cuerpo no necesita azúcar, necesita energía y calma. Si tienes antojo, disfrútalo, pero combínalo con algo de proteína como yogur para sentirte satisfecho más tiempo. En lugar de registrar calorías manualmente, solo tómale una foto a tu plato al bot de FoodFlow (@FoodFlow2026bot) y calculará tus macros al instante sin complicaciones. ¿Cuál es tu antojo de media tarde favorito?",
            "image_prompt": "Professional lifestyle photography of a fresh sliced avocado, lime, and healthy tacos on a warm wooden dining table, subtle warm neon highlights, 8k resolution, vertical shot --ar 4:5",
        }
    return dict(B2B_FALLBACK if b2b else {
        "topic": "Как победить чувство вины за эмоциональные перекусы",
        "text": "Снова рука потянулась к печенью на работе? Хватит винить себя за срывы. Твоему организму часто не хватает не сахара, а просто сытости. А если хочется конфету — съешь, но добавь к ней белок (например йогурт), так сытость останется надолго. Вместо ручного ввода калорий просто сфотографируй тарелку для бота FoodFlow (@FoodFlow2026bot), он за секунду разложит КБЖУ без страданий! А какой перекус спасает тебя на работе?",
        "image_prompt": "Professional lifestyle photography of a healthy bowl of Greek yogurt with blue berries, fresh sliced almonds and honey on a dark wooden office table, subtle teal and pink neon highlights, 8k resolution, vertical shot --ar 4:5",
    })


async def save_image_file(img_url: str, output_path: Path):
    """
    Saves an image from either base64 string or HTTP URL to a local file.
    """
    if img_url.startswith("data:image"):
        try:
            fmt, imgstr = img_url.split(';base64,')
            with open(output_path, "wb") as f:
                f.write(base64.b64decode(imgstr))
            logger.info(f"💾 Успешно декодирована и сохранена картинка Base64 в {output_path.name}")
        except Exception as e:
            logger.error(f"❌ Ошибка декодирования Base64: {e}")
            raise
    else:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(img_url, timeout=30) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        with open(output_path, "wb") as f:
                            f.write(data)
                        logger.info(f"💾 Успешно скачана и сохранена картинка по ссылке в {output_path.name}")
                    else:
                        raise RuntimeError(f"Failed to download image: HTTP {resp.status}")
        except Exception as e:
            logger.error(f"❌ Ошибка скачивания картинки: {e}")
            raise

async def create_autonomous_morning_shorts_run(locale: str = "ru") -> Path:
    """
    Full workflow to create a morning autonomous runs directory, generate bases, image and post.json.
    Supports locale='ru' and locale='es'.
    """
    b2b = is_b2b_shorts_slot() if locale == "ru" else False
    basis = await generate_shorts_basis(b2b=b2b, locale=locale)

    runs_dir = Path("/home/user1/foodflow-bot_new/content_factory/runs")
    runs_dir.mkdir(parents=True, exist_ok=True)

    utc_now = datetime.now(timezone.utc)
    if locale == "es":
        suffix = "autonomous_morning_shorts_es"
    elif b2b:
        suffix = "autonomous_morning_shorts_b2b"
    else:
        suffix = "autonomous_morning_shorts"
    dir_name = f"{utc_now.strftime('%Y%m%dT%H%M%SZ')}_{suffix}"
    run_dir = runs_dir / dir_name
    run_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(
        f"📁 Создана утренняя автономная директория: {run_dir.name}"
        + (" [B2B curator weekly]" if b2b else "")
    )
    
    try:
        # 3. Generate image using image_prompt
        img_url = await generate_image(basis["image_prompt"])
        image_png_path = run_dir / "image.png"
        
        if img_url:
            await save_image_file(img_url, image_png_path)
        else:
            # Fallback to copy default past post image reference if generation completely failed
            default_ref = Path("/home/user1/foodflow-bot_new/content_factory/image_refs/ref_past_post.png")
            if default_ref.exists():
                import shutil
                shutil.copy2(default_ref, image_png_path)
                logger.warning("⚠️ Не удалось сгенерировать картинку, скопирован дефолтный референс.")
            else:
                raise FileNotFoundError("Image generation failed and no fallback reference image found!")
                
        # 4. Save post.json
        post_data = {
            "created_at_utc": utc_now.strftime("%Y%m%dT%H%M%SZ"),
            "mode": "channel",
            "locale": locale,
            "topic": basis["topic"],
            "scenario": "b2b_curator_pitch" if b2b else ("useful_tip_es" if locale == "es" else "useful_tip"),
            "audience": "b2b_curator" if b2b else "b2c",
            "text": basis["text"],
            "image_prompt": basis["image_prompt"],
            "image_ref": str(image_png_path),
            "publish_target_chat_id": -1003856929949,  # default foodflow channel
            "saved_image_path": str(image_png_path)
        }
        if "series" in basis:
            post_data["series"] = basis["series"]
        
        # Mock publish.json to simulate successful Telegram publication for the analyst
        publish_data = {
            "ok": True,
            "mode": "channel",
            "message_id": 9999,
            "chat_id": -1003856929949,
            "topic": basis["topic"]
        }
        
        with open(run_dir / "post.json", "w", encoding="utf-8") as f:
            json.dump(post_data, f, indent=2, ensure_ascii=False)
            
        with open(run_dir / "publish.json", "w", encoding="utf-8") as f:
            json.dump(publish_data, f, indent=2, ensure_ascii=False)
            
        logger.info("✅ Директория автономного Shorts укомплектована (post.json, publish.json, image.png)")
        return run_dir
    except Exception as e:
        import shutil
        logger.error(f"❌ Сбой при укомплектовании директории {run_dir.name}, удаляем пустую директорию: {e}")
        shutil.rmtree(run_dir, ignore_errors=True)
        raise

def calculate_today_12_00_msk_publish_time() -> str:
    """
    Calculates today's or tomorrow's 12:00 MSK schedule time.
    Returns ISO 8601 UTC string.
    """
    now_msk = datetime.now(MOSCOW_TZ)
    target_msk = now_msk.replace(hour=12, minute=0, second=0, microsecond=0)
    
    if now_msk >= target_msk:
        target_msk += timedelta(days=1)
        
    target_utc = target_msk.astimezone(timezone.utc)
    return target_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

def calculate_today_12_30_msk_publish_time() -> str:
    """
    Calculates today's or tomorrow's 12:30 MSK schedule time.
    Returns ISO 8601 UTC string.
    """
    now_msk = datetime.now(MOSCOW_TZ)
    target_msk = now_msk.replace(hour=12, minute=30, second=0, microsecond=0)
    
    if now_msk >= target_msk:
        target_msk += timedelta(days=1)
        
    target_utc = target_msk.astimezone(timezone.utc)
    return target_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

async def run_morning_shorts_pipeline(locale: str = "ru"):
    """
    Main entry point for morning pipeline: generates the basis, sets env vars and triggers worker.
    Supports locale='ru' (Russian, 12:00 MSK) and locale='es' (Spanish/LATAM, 12:30 MSK).
    """
    tag = "ES/LATAM" if locale == "es" else "RU"
    logger.info(f"🚀 ЗАПУСК ПОЛНОГО УТРЕННЕГО АВТОНОМНОГО SHORTS-КОНВЕЙЕРА [{tag}]...")
    try:
        # Create run basis and directory
        run_dir = await create_autonomous_morning_shorts_run(locale=locale)

        # Calculate scheduling target
        if os.environ.get("SHORTS_PUBLISH_AT_OVERRIDE") == "immediate":
            publish_time_utc = "immediate"
            logger.info("🚀 Publishing immediately (immediate override)")
        elif locale == "es":
            publish_time_utc = calculate_today_12_30_msk_publish_time()
            logger.info(f"⏳ Publicación programada en YouTube ES: {publish_time_utc} UTC (12:30 MSK)")
        else:
            publish_time_utc = calculate_today_12_00_msk_publish_time()
            logger.info(f"⏳ Расписание публикации YouTube/VK: {publish_time_utc} UTC (12:00 MSK)")

        # Set environment variables for the worker
        os.environ["SHORTS_FORCE_RUN_DIR"] = str(run_dir.resolve())
        os.environ["SHORTS_PUBLISH_AT"] = publish_time_utc
        os.environ["SHORTS_LOCALE"] = locale

        # Import and run the unified shorts worker (checkpoint-aware)
        from content_factory.shorts_generator.worker import main as run_shorts_worker
        await run_shorts_worker()

        logger.info(f"🎉 УТРЕННИЙ АВТОНОМНЫЙ SHORTS-КОНВЕЙЕР [{tag}] ЗАВЕРШИЛ РАБОТУ УСПЕШНО!")

    except Exception as e:
        logger.error(f"❌ Критический сбой утреннего автономного Shorts-конвейера [{tag}]: {e}", exc_info=True)
        raise
    finally:
        # Prevent environment pollution across scheduler jobs running in the same process
        os.environ.pop("SHORTS_FORCE_RUN_DIR", None)
        os.environ.pop("SHORTS_PUBLISH_AT", None)
        os.environ.pop("SHORTS_LOCALE", None)
