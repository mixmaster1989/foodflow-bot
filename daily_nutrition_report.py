#!/usr/bin/env python3
"""
Daily Nutrition Report - Ежедневный отчёт нутрициолога

Запускается cron'ом в 12:00 МСК.
Собирает данные о питании за вчера, анализирует через Gemini 3 Flash,
генерирует красивую карточку (Pillow) и отправляет фото с отчетом.

ТЕСТОВЫЙ РЕЖИМ: только для админа или указанного ID
"""

import asyncio
import re
import html
import logging
import aiohttp
from datetime import datetime, timedelta
from pathlib import Path
import sys
from io import BytesIO

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import select, and_
from database.base import get_db
from database.models import ConsumptionLog, User, UserSettings
from config import settings
from services.image_renderer import draw_daily_card

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
TARGET_TEST_ID = None # 5422141137 # Set this to Olga's ID if known for testing

# Модели с фоллбеками
MODELS = [
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
- Калории: ~2000 ккал (или цель пользователя)

📝 ЗАДАЧА:
Сформируй отчёт СТРОГО по шаблону:

✅ <b>Сильные стороны:</b>
• [1-2 пункта что было хорошо]

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
5. Тон: дружелюбный, профессиональный, без осуждения.
6. Длина: 10-12 строк. БЕЗ приветствий и заголовков (они есть на картинке).

Верни ТОЛЬКО готовый HTML-текст."""

# =====================================================
# Функции санитизации HTML
# =====================================================

def sanitize_telegram_html(text: str) -> str:
    """Удаляет неподдерживаемые теги, сохраняя разрешённые."""
    if not text:
        return ""
    text = re.sub(r'^```html?\s*\n?', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n?```\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    
    def replace_tag(match):
        full_tag = match.group(0)
        tag_name = match.group(1).lower().split()[0]
        if tag_name.startswith('/'): tag_name = tag_name[1:]
        if tag_name in ALLOWED_TAGS: return full_tag
        return ''
    
    text = re.sub(r'<(/?\w+)[^>]*>', replace_tag, text)
    
    # Simple escape check (not perfect but sufficient for now)
    return text.strip()

def validate_html_tags(text: str) -> bool:
    """Проверяет что все теги закрыты корректно."""
    stack = []
    tag_pattern = re.compile(r'<(/?)(\w+)[^>]*>')
    for match in tag_pattern.finditer(text):
        is_closing = match.group(1) == '/'
        tag_name = match.group(2).lower()
        if tag_name not in ALLOWED_TAGS: continue
        if is_closing:
            if not stack or stack[-1] != tag_name: return False
            stack.pop()
        else:
            stack.append(tag_name)
    return len(stack) == 0

# =====================================================
# OpenRouter API
# =====================================================

async def call_openrouter(model: str, prompt: str) -> str | None:
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
        "max_tokens": 800
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(OPENROUTER_URL, json=payload, headers=headers, timeout=30) as resp:
                if resp.status != 200:
                    logger.error(f"OpenRouter error {resp.status}: {await resp.text()}")
                    return None
                data = await resp.json()
                return data.get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception as e:
        logger.error(f"OpenRouter request failed: {e}")
        return None

async def get_nutrition_report(food_data: dict, retries: int = 2) -> str:
    prompt = NUTRITION_PROMPT.format(**food_data)
    for attempt in range(retries):
        for model in MODELS:
            response = await call_openrouter(model, prompt)
            if not response: continue
            sanitized = sanitize_telegram_html(response)
            if validate_html_tags(sanitized):
                return sanitized
            logger.warning(f"Invalid HTML from {model}, trying next...")
    return None

# =====================================================
# Сбор данных из базы
# =====================================================

async def get_yesterday_data(user_id: int):
    """Получает полные данные за вчера: логи, цели, имя."""
    yesterday = datetime.utcnow().date() - timedelta(days=1)
    
    async for session in get_db():
        # 1. Get User Name
        user = await session.get(User, user_id)
        user_name = user.first_name if user else "User"
        
        # 2. Get Settings (Goals)
        stmt_settings = select(UserSettings).where(UserSettings.user_id == user_id)
        users_settings = (await session.execute(stmt_settings)).scalar_one_or_none()
        goals = {
            "calories": users_settings.calorie_goal if users_settings else 2000,
            "protein": users_settings.protein_goal if users_settings else 100,
            "fat": users_settings.fat_goal if users_settings else 70,
            "carbs": users_settings.carb_goal if users_settings else 250,
            "fiber": users_settings.fiber_goal if users_settings else 30
        }

        # 3. Get Logs
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
    
    # Aggregate
    total_cal = sum(log.calories or 0 for log in logs)
    total_prot = sum(log.protein or 0 for log in logs)
    total_fat = sum(log.fat or 0 for log in logs)
    total_carb = sum(log.carbs or 0 for log in logs)
    total_fiber = sum(log.fiber or 0 for log in logs)
    
    # Format for AI Prompt
    food_list_text = "\n".join([f"• {l.product_name}: {int(l.calories or 0)} ккал" for l in logs])
    
    return {
        "user_name": user_name,
        "date": yesterday,
        "logs": logs, # Raw objects for Image
        "totals": {
            "calories": total_cal,
            "protein": total_prot,
            "fat": total_fat,
            "carbs": total_carb,
            "fiber": total_fiber
        },
        "goals": goals,
        "prompt_data": { # Data for text prompt
            "date": yesterday.strftime("%d.%m.%Y"),
            "food_list": food_list_text if food_list_text else "Нет данных",
            "total_cal": int(total_cal),
            "total_prot": round(total_prot, 1),
            "total_fat": round(total_fat, 1),
            "total_carb": round(total_carb, 1)
        }
    }

# =====================================================
# Отправка фото в Telegram
# =====================================================

async def send_telegram_photo(user_id: int, image_bio: BytesIO, caption: str) -> bool:
    """Отправляет фото с описанием пользователю."""
    url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendPhoto"
    
    # We use aiohttp.FormData to send multipart/form-data
    data = aiohttp.FormData()
    data.add_field('chat_id', str(user_id))
    data.add_field('caption', caption)
    data.add_field('parse_mode', 'HTML')
    data.add_field('photo', image_bio, filename='report.png', content_type='image/png')
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data, timeout=30) as resp:
                if resp.status != 200:
                    logger.error(f"Telegram Photo Error {resp.status}: {await resp.text()}")
                    return False
                return True
    except Exception as e:
        logger.error(f"Telegram photo send failed: {e}")
        return False

# =====================================================
# Main Logic
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
        return [row[0] for row in result.fetchall()]

async def run_daily_report():
    logger.info("=" * 50)
    logger.info("Starting Visual Daily Nutrition Report")
    logger.info(f"Test Mode: {TEST_MODE}")
    logger.info("=" * 50)
    
    # 1. Determine Target Users
    user_ids = []
    if TEST_MODE:
        if TARGET_TEST_ID:
            user_ids = [TARGET_TEST_ID]
            logger.info(f"TEST MODE: Targeting ONLY {TARGET_TEST_ID}")
        else:
            # Fallback to Admin if self-test
            all_users = await get_users_with_yesterday_data()
            if ADMIN_ID in all_users: user_ids = [ADMIN_ID]
            logger.info(f"TEST MODE: Targeting Admin {ADMIN_ID}")
    else:
        user_ids = await get_users_with_yesterday_data()
        logger.info(f"Found {len(user_ids)} users with data")

    if not user_ids:
        logger.info("No users found. Exiting.")
        return

    # 2. Process Queue
    for user_id in user_ids:
        logger.info(f"Processing user {user_id}...")
        try:
            # A. Get Data
            data = await get_yesterday_data(user_id)
            if not data: continue
            
            # B. Generate AI Text Report
            report_text = await get_nutrition_report(data['prompt_data'])
            if not report_text:
                # Fallback text if AI fails
                report_text = "📊 <b>Ваш отчет готов!</b>\nПодробности на изображении 👆"
            
            # C. Generate Image (Pillow)
            image_bio = draw_daily_card(
                user_name=data['user_name'],
                target_date=data['date'],
                logs=data['logs'],
                total_metrics=data['totals'],
                goals=data['goals']
            )
            
            # D. Send
            success = await send_telegram_photo(user_id, image_bio, report_text)
            if success:
                logger.info(f"✅ Report sent to {user_id}")
            else:
                logger.error(f"❌ Failed to send to {user_id}")
                
        except Exception as e:
            logger.error(f"Error processing user {user_id}: {e}", exc_info=True)
        
        await asyncio.sleep(1.0) # Rate limit protection

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run daily nutrition report")
    parser.add_argument("--test", type=int, help="Run in test mode for specific user ID")
    parser.add_argument("--admin", action="store_true", help="Run in test mode for Admin")
    args = parser.parse_args()

    if args.test:
        TEST_MODE = True
        TARGET_TEST_ID = args.test
    elif args.admin:
        TEST_MODE = True
        TARGET_TEST_ID = ADMIN_ID
        
    asyncio.run(run_daily_report())
