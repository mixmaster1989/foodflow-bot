#!/usr/bin/env python3
"""
Daily Nutrition Report - Ежедневный отчёт нутрициолога

Запускается cron'ом в 12:00 МСК.
Собирает данные о питании за вчера, анализирует через Gemini 3 Flash,
отправляет персональный отчёт пользователю.

ТЕСТОВЫЙ РЕЖИМ: только для админа (432823154)
"""

import asyncio
import re
import html
import logging
import aiohttp
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import select, and_
from database.base import get_db
from database.models import ConsumptionLog, User, UserSettings
from config import settings

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =====================================================
# Конфигурация
# =====================================================

# ПРОДАКШН РЕЖИМ
TEST_MODE = False
ADMIN_ID = 432823154

# Модели с фоллбеками
MODELS = [
    "google/gemini-3-flash-preview",
    "google/gemini-2.5-flash",
    "google/gemini-2.0-flash-exp:free"
]

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Разрешённые HTML-теги для Telegram
ALLOWED_TAGS = {'b', 'strong', 'i', 'em', 'u', 'ins', 's', 'strike', 'del', 
                'code', 'pre', 'a', 'tg-spoiler'}

# =====================================================
# Промпт для нутрициолога
# =====================================================

NUTRITION_PROMPT = """Ты — AI-нутрициолог, анализирующий питание пользователя.

📊 ДАННЫЕ ЗА {date}:
{food_list}

ИТОГО за день:
🔥 Калории: {total_cal} ккал
🥩 Белки: {total_prot}г
🥑 Жиры: {total_fat}г
🍞 Углеводы: {total_carb}г

📋 РЕКОМЕНДУЕМЫЕ НОРМЫ:
- Калории: ~2000 ккал
- Белки: ~100г
- Жиры: ~70г
- Углеводы: ~250г

📝 ЗАДАЧА:
Сформируй отчёт СТРОГО по шаблону:

📊 <b>Итоги дня {date}</b>

🔥 Калории: {total_cal} / 2000 ккал
🥩 Белки: {total_prot}г / 100г
🥑 Жиры: {total_fat}г / 70г
🍞 Углеводы: {total_carb}г / 250г

✅ <b>Сильные стороны:</b>
• [1-2 пункта что было хорошо в питании]

⚠️ <b>Слабые стороны:</b>
• [1-2 пункта что можно улучшить]

💡 <b>Совет на сегодня:</b>
[Один конкретный практический совет]

📈 <b>Оценка дня:</b> X/10

ПРАВИЛА ФОРМАТИРОВАНИЯ:
1. Используй ТОЛЬКО эти HTML-теги: <b>, <i>, <u>, <s>, <code>, <a>, <tg-spoiler>
2. Для переноса строки используй обычный перенос (Enter)
3. Для списков используй • или - 
4. НЕ используй: <p>, <div>, <span>, <ul>, <li>, <h1>-<h6>, <font>, <br>
5. Экранируй спецсимволы в тексте: < → &lt; > → &gt; & → &amp;
6. Тон: нейтральный, информативный, без осуждения
7. Длина: 10-15 строк

Верни ТОЛЬКО готовый HTML-текст для Telegram, без обёрток, ```html``` и пояснений."""

# =====================================================
# Функции санитизации HTML
# =====================================================

def sanitize_telegram_html(text: str) -> str:
    """Удаляет неподдерживаемые теги, сохраняя разрешённые."""
    
    if not text:
        return ""
    
    # 1. Убираем markdown code blocks если модель их добавила
    text = re.sub(r'^```html?\s*\n?', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n?```\s*$', '', text, flags=re.MULTILINE)
    
    # 2. Заменяем <br> на \n
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    
    # 3. Удаляем неподдерживаемые теги (сохраняя контент)
    def replace_tag(match):
        full_tag = match.group(0)
        tag_name = match.group(1).lower().split()[0]
        
        # Проверяем закрывающий тег
        if tag_name.startswith('/'):
            tag_name = tag_name[1:]
        
        if tag_name in ALLOWED_TAGS:
            return full_tag  # Оставляем как есть
        return ''  # Удаляем тег
    
    text = re.sub(r'<(/?\w+)[^>]*>', replace_tag, text)
    
    # 4. Сохраняем валидные теги временно
    placeholder = {}
    counter = [0]
    
    def save_tag(m):
        key = f"__TAG_{counter[0]}__"
        placeholder[key] = m.group(0)
        counter[0] += 1
        return key
    
    allowed_pattern = '|'.join(ALLOWED_TAGS)
    tag_regex = rf'</?(?:{allowed_pattern})(?:\s[^>]*)?>'
    text = re.sub(tag_regex, save_tag, text, flags=re.IGNORECASE)
    
    # 5. Экранируем опасные символы вне тегов
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    
    # 6. Возвращаем теги на место
    for key, val in placeholder.items():
        escaped_key = key.replace('&', '&amp;')
        text = text.replace(escaped_key, val)
    
    return text.strip()


def validate_html_tags(text: str) -> bool:
    """Проверяет что все теги закрыты корректно."""
    stack = []
    tag_pattern = re.compile(r'<(/?)(\w+)[^>]*>')
    
    for match in tag_pattern.finditer(text):
        is_closing = match.group(1) == '/'
        tag_name = match.group(2).lower()
        
        if tag_name not in ALLOWED_TAGS:
            continue
            
        if is_closing:
            if not stack or stack[-1] != tag_name:
                return False
            stack.pop()
        else:
            stack.append(tag_name)
    
    return len(stack) == 0


# =====================================================
# OpenRouter API
# =====================================================

async def call_openrouter(model: str, prompt: str) -> str | None:
    """Вызов OpenRouter API."""
    
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://foodflow.bot",
        "X-Title": "FoodFlow Nutrition Report"
    }
    
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 1000
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(OPENROUTER_URL, json=payload, headers=headers, timeout=30) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    logger.error(f"OpenRouter error {resp.status}: {error}")
                    return None
                
                data = await resp.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                return content
                
    except Exception as e:
        logger.error(f"OpenRouter request failed: {e}")
        return None


async def get_nutrition_report(food_data: dict, retries: int = 2) -> str:
    """Получает отчёт от AI с ретраями и фоллбеками."""
    
    # Формируем промпт
    prompt = NUTRITION_PROMPT.format(**food_data)
    
    for attempt in range(retries):
        for model in MODELS:
            logger.info(f"Trying model: {model} (attempt {attempt + 1})")
            
            response = await call_openrouter(model, prompt)
            
            if not response:
                continue
            
            # Санитизация
            sanitized = sanitize_telegram_html(response)
            
            # Валидация
            if validate_html_tags(sanitized):
                logger.info(f"Success with model: {model}")
                return sanitized
            else:
                logger.warning(f"Invalid HTML from {model}, trying next...")
                continue
    
    # Все модели не справились — возвращаем None (ТИШИНА для пользователя)
    logger.error("All models failed, returning None (SILENT)")
    return None


def generate_plain_fallback(food_data: dict) -> str:
    """Генерирует простой текстовый отчёт без AI."""
    return (
        f"📊 <b>Итоги дня {food_data['date']}</b>\n\n"
        f"🔥 Калории: {food_data['total_cal']} ккал\n"
        f"🥩 Белки: {food_data['total_prot']}г\n"
        f"🥑 Жиры: {food_data['total_fat']}г\n"
        f"🍞 Углеводы: {food_data['total_carb']}г\n\n"
        f"<i>AI-анализ временно недоступен.</i>"
    )


# =====================================================
# Сбор данных из базы
# =====================================================

async def get_yesterday_consumption(user_id: int) -> dict | None:
    """Получает данные о питании за вчера."""
    
    yesterday = datetime.utcnow().date() - timedelta(days=1)
    
    async for session in get_db():
        stmt = select(ConsumptionLog).where(
            and_(
                ConsumptionLog.user_id == user_id,
                ConsumptionLog.date >= datetime.combine(yesterday, datetime.min.time()),
                ConsumptionLog.date < datetime.combine(yesterday + timedelta(days=1), datetime.min.time())
            )
        )
        result = await session.execute(stmt)
        logs = result.scalars().all()
    
    if not logs:
        return None
    
    # Агрегируем данные
    total_cal = sum(log.calories or 0 for log in logs)
    total_prot = sum(log.protein or 0 for log in logs)
    total_fat = sum(log.fat or 0 for log in logs)
    total_carb = sum(log.carbs or 0 for log in logs)
    
    # Форматируем список еды
    food_items = []
    for log in logs:
        food_items.append(f"• {log.product_name}: {int(log.calories or 0)} ккал")
    
    return {
        "date": yesterday.strftime("%d.%m.%Y"),
        "food_list": "\n".join(food_items) if food_items else "Нет данных",
        "total_cal": int(total_cal),
        "total_prot": round(total_prot, 1),
        "total_fat": round(total_fat, 1),
        "total_carb": round(total_carb, 1)
    }


# =====================================================
# Отправка сообщения в Telegram
# =====================================================

async def send_telegram_message(user_id: int, text: str) -> bool:
    """Отправляет сообщение пользователю."""
    
    url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage"
    
    payload = {
        "chat_id": user_id,
        "text": text,
        "parse_mode": "HTML"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=10) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    logger.error(f"Telegram error: {error}")
                    return False
                return True
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")
        return False


# =====================================================
# Главная функция — очередь: сначала собрать ВСЕ, потом отправить
# =====================================================

async def get_users_with_yesterday_data() -> list[int]:
    """Получает список user_id у кого есть данные за вчера."""
    yesterday = datetime.utcnow().date() - timedelta(days=1)
    
    async for session in get_db():
        from sqlalchemy import distinct
        stmt = select(distinct(ConsumptionLog.user_id)).where(
            and_(
                ConsumptionLog.date >= datetime.combine(yesterday, datetime.min.time()),
                ConsumptionLog.date < datetime.combine(yesterday + timedelta(days=1), datetime.min.time())
            )
        )
        result = await session.execute(stmt)
        user_ids = [row[0] for row in result.fetchall()]
    
    return user_ids


async def run_daily_report():
    """Запускает ежедневный отчёт с очередью."""
    
    logger.info("=" * 50)
    logger.info("Starting Daily Nutrition Report")
    logger.info(f"Test Mode: {TEST_MODE}")
    logger.info("=" * 50)
    
    # ===== ШАГ 1: Определяем пользователей =====
    if TEST_MODE:
        # Тестовый режим — только админ, если у него есть данные
        all_users_with_data = await get_users_with_yesterday_data()
        if ADMIN_ID in all_users_with_data:
            user_ids = [ADMIN_ID]
        else:
            logger.info(f"Admin {ADMIN_ID} has no data for yesterday, nothing to do")
            return
        logger.info(f"Test mode: processing only admin {ADMIN_ID}")
    else:
        # Продакшн — все у кого есть данные за вчера
        user_ids = await get_users_with_yesterday_data()
        logger.info(f"Found {len(user_ids)} users with yesterday's data")
    
    if not user_ids:
        logger.info("No users with data for yesterday, exiting")
        return
    
    # ===== ШАГ 2: Собираем ВСЕ отчёты (очередь) =====
    reports_queue: list[tuple[int, str]] = []  # (user_id, report_text)
    
    for user_id in user_ids:
        logger.info(f"[COLLECT] Processing user {user_id}...")
        
        try:
            # Получаем данные за вчера
            food_data = await get_yesterday_consumption(user_id)
            
            if not food_data:
                logger.warning(f"[COLLECT] No food data for user {user_id}, skipping")
                continue
            
            # Получаем отчёт от AI
            report = await get_nutrition_report(food_data)
            
            # Проверяем что отчёт валидный (не пустой и не fallback с ошибкой)
            if report and len(report) > 50:  # Минимальная длина валидного отчёта
                reports_queue.append((user_id, report))
                logger.info(f"[COLLECT] Report ready for user {user_id} ({len(report)} chars)")
            else:
                # ТИШИНА для пользователя — только лог
                logger.error(f"[COLLECT] Invalid/empty report for user {user_id}, SILENT skip")
                
        except Exception as e:
            # ТИШИНА для пользователя — только лог
            logger.error(f"[COLLECT] Error for user {user_id}: {e}, SILENT skip")
            continue
        
        # Пауза между запросами к AI (rate limit)
        await asyncio.sleep(1.0)
    
    logger.info(f"[COLLECT] Queue ready: {len(reports_queue)} reports to send")
    
    # ===== ШАГ 3: Отправляем ВСЕ собранные отчёты =====
    success_count = 0
    error_count = 0
    
    for user_id, report in reports_queue:
        try:
            if await send_telegram_message(user_id, report):
                logger.info(f"[SEND] Report sent to user {user_id}")
                success_count += 1
            else:
                # Ошибка отправки — только лог, ТИШИНА
                logger.error(f"[SEND] Failed to send to user {user_id}, SILENT")
                error_count += 1
        except Exception as e:
            logger.error(f"[SEND] Exception for user {user_id}: {e}, SILENT")
            error_count += 1
        
        # Пауза между отправками
        await asyncio.sleep(0.3)
    
    # ===== Итоги =====
    logger.info("=" * 50)
    logger.info(f"Report complete:")
    logger.info(f"  - Users with data: {len(user_ids)}")
    logger.info(f"  - Reports collected: {len(reports_queue)}")
    logger.info(f"  - Successfully sent: {success_count}")
    logger.info(f"  - Send errors (silent): {error_count}")
    logger.info("=" * 50)


# =====================================================
# Entry point
# =====================================================

if __name__ == "__main__":
    asyncio.run(run_daily_report())

