import asyncio
import json
import logging
import os
import sys
import aiohttp
from datetime import datetime

# Добавляем путь к корню проекта
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ГРУППА "ЗЕЛЕНАЯ" (Много данных)
GREEN_IDS = [5422141137, 295543071, 5153798702, 104202119]

# МОДЕЛИ
MODEL_ANALYST = "openai/gpt-5.4"
MODEL_STYLIST = "anthropic/claude-4.6-sonnet"

# ПРОКСИ
PROXY_URL = "http://3mqY3B:eYoGPf@138.122.195.71:8000"

# ПРОМПТЫ
PROMPT_ANALYST = """
Ты — старший клинический нутрициолог. Проанализируй данные пользователя и составь сухой, максимально точный экспертный отчет.
ДАННЫЕ:
- Имя: {name}, Возраст: {age}, Вес: {weight} кг, Цель: {goal}
- КБЖУ цели: {cal} ккал (Б:{prot}, Ж:{fat}, У:{carb})
ЛОГИ ПИТАНИЯ:
{logs_summary}
ДИНАМИКА ВЕСА:
{weight_dynamics}

ЗАДАЧА:
1. Оцени фактическое потребление КБЖУ относительно цели.
2. Выяви дефициты минералов или профицит вредных продуктов.
3. Проанализируй влияние питания на динамику веса.
4. Дай 5 жестких, научно-обоснованных рекомендаций.
Ответ дай в виде структурированного экспертного заключения (сухие факты).
"""

PROMPT_STYLIST = """
Перед тобой сухой медицинский отчет для женщины к 8 марта. 
Твоя задача: переписать его так, чтобы это выглядело как теплый, вдохновляющий и мега-полезный ПОДАРОК от команды "FoodFlow".

ПРАВИЛА:
1. Сохрани ВСЕ важные медицинские факты и советы из отчета.
2. Тон: Исключительно доброжелательный, эмпатичный, современный (Big Tech стиль).
3. Формат:
   - Красивое поздравление с 8 марта.
   - Раздел "Твой путь": анализ прогресса и еды (человеческим языком).
   - Раздел "Секреты для тебя": полезные советы, преподнесенные как забота.
   - Теплое напутствие.
4. Убери "сухость", добавь "души", но не лей воду.

ИСХОДНЫЙ ОТЧЕТ:
{raw_analysis}
"""

async def call_openrouter(model, prompt):
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://foodflow.app",
        "X-Title": "FoodFlow Bot"
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}]
    }
    
    # Используем прокси для преодоления региональных ограничений
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                proxy=PROXY_URL,
                timeout=120
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return result['choices'][0]['message']['content']
                else:
                    err = await response.text()
                    logger.error(f"Error {model}: {response.status} - {err}")
                    return None
        except Exception as e:
            logger.error(f"Exc {model}: {e}")
            return None

def summarize_logs(logs):
    if not logs: return "Нет данных."
    products = {}
    for l in logs:
        p = l['product']
        products[p] = products.get(p, 0) + 1
    top_p = ", ".join([f"{k}({v})" for k,v in sorted(products.items(), key=lambda x:x[1], reverse=True)[:10]])
    return f"Записей: {len(logs)}. Топ: {top_p}"

def summarize_weight(weight_logs):
    if not weight_logs: return "Нет данных."
    w = [log['weight'] for log in weight_logs]
    return f"Старт: {w[0]}, Текущий: {w[-1]}, Динамика: {w[-1]-w[0]:+.1f} кг"

async def generate_full_gift(user_json):
    name = f"{user_json['profile']['first_name']} {user_json['profile']['last_name'] or ''}".strip()
    sd = user_json.get('settings', {})
    
    # Шаг 1: Анализ (GPT-5.4)
    logger.info(f"--- Шаг 1: Анализ для {name} (GPT-5.4) ---")
    analysis_prompt = PROMPT_ANALYST.format(
        name=name, age=sd.get('age', 'N/A'), weight=sd.get('weight', 'N/A'),
        goal=sd.get('goal', 'lose_weight'), cal=sd.get('calorie_goal', 0),
        prot=sd.get('protein_goal', 0), fat=sd.get('fat_goal', 0), carb=sd.get('carb_goal', 0),
        logs_summary=summarize_logs(user_json.get('consumption_logs', [])),
        weight_dynamics=summarize_weight(user_json.get('weight_logs', []))
    )
    raw_analysis = await call_openrouter(MODEL_ANALYST, analysis_prompt)
    if not raw_analysis: return None

    # Шаг 2: Стилизация (Claude 4.6)
    logger.info(f"--- Шаг 2: Стилизация для {name} (Claude 4.6) ---")
    style_prompt = PROMPT_STYLIST.format(raw_analysis=raw_analysis)
    final_gift = await call_openrouter(MODEL_STYLIST, style_prompt)
    
    return final_gift

async def main():
    logger.info("🚀 Запуск генератора подарков ЭЛИТ уровня (с ПРОКСИ)...")
    with open('data/march_8_stats.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    output_path = "data/march_8_ai_gifts_v2.json"
    gifts = {}
    if os.path.exists(output_path):
        with open(output_path, "r", encoding="utf-8") as f:
            gifts = json.load(f)
            logger.info(f"Загружено {len(gifts)} уже готовых отчетов.")

    for user in data:
        u_id = str(user['user_id'])
        if int(u_id) in GREEN_IDS and u_id not in gifts:
            gift = await generate_full_gift(user)
            if gift:
                gifts[u_id] = gift
                logger.info(f"✅ Финальный отчет для {user['profile']['first_name']} готов!")
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(gifts, f, ensure_ascii=False, indent=2)
            await asyncio.sleep(2)

    logger.info(f"🏁 Все подарки готовы ({len(gifts)} шт).")

if __name__ == "__main__":
    asyncio.run(main())
