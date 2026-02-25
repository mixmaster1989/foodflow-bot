#!/usr/bin/env python3
import asyncio
import logging
import sys
import os
from pathlib import Path

# Add root directory to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from sqlalchemy import select

from config import settings
from database.base import init_db, get_db
from database.models import User

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
DRY_RUN = False  # Set to False to actually send messages
TEST_MODE = False # Set to True to send only to specific test IDs
TEST_USER_IDS = [432823154] # Igor's ID

USER_MESSAGE = """🚀 <b>Эволюция FoodFlow: Становимся лучше вместе!</b>

Этот проект растет благодаря тебе. Мы внимательно читали каждый отзыв и внесли изменения, которые сделают твой путь к здоровью еще приятнее:

✅ <b>Минимализм и фокус:</b> Мы навели порядок в меню, убрав всё лишнее. Теперь интерфейс легкий и интуитивный — только ты и твои цели. 🧹
✅ <b>Умный баланс воды:</b> Мы полностью переосмыслили контроль воды! Бот теперь сам рассчитывает твою норму, исходя из твоих личных целей и параметров. Пей вовремя и следи за индикатором! 💧🐳
✅ <b>Понимаем с полуслова:</b> Больше не нужно ломать голову над граммами. Пиши "один банан", "стакан сока" или "порция борща" — бот сам всё сконвертирует. 🍎🍏
✅ <b>Безопасность и порядок:</b> Твои ссылки-приглашения стали еще надежнее, защищая приватность твоего прогресса. ⏳

🛡️ <b>Три уровня твоей уверенности:</b>
    *   🍦 <b>Lite (Базовый):</b> Весь основной трекинг (текст, вода, вес) навсегда бесплатен. Это твой надежный фундамент.
    *   ⚡ <b>Basic (Комфорт):</b> Всё из Lite + магия <b>Голосового ввода</b>, полное управление уведомлениями и удобство Mini App.
    *   💎 <b>Pro (Максимум):</b> Всё из Basic + <b>AI-анализ</b> фото, автоматический Холодильник и персональные советы от нейро-диетолога.

❤️ <b>Наше «Спасибо» первопроходцам:</b> Мы бесконечно благодарны тебе за то, что ты помогаешь нам создавать этот продукт. В знак признательности, всем нашим текущим тестерам мы дарим <b>1 месяц PRO-подписки</b> сразу после релиза! А сейчас — наслаждайся всеми PRO-функциями абсолютно бесплатно.

<i>Расцветай вместе с FoodFlow! 🥗✨</i>"""

CURATOR_MESSAGE_ADDON = """---

👨‍🏫 <b>КАБИНЕТ КУРАТОРА 2.0: ПОЛНЫЙ КОНТРОЛЬ!</b>

Коллеги, мы выкатили мощное обновление системы ведения подопечных. Теперь у вас в руках настоящие инструменты управления:

✅ <b>🗑 Удаление подопечных:</b> Теперь вы можете официально "отпустить" пользователя. В его карточке появилась кнопка удаления. После подтверждения связь разрывается, юзер уведомляется, но вся его история остается у него. Чисто и профессионально.
✅ <b>⏳ Временные ссылки (1-30 дней):</b> При генерации реферальной ссылки или приглашения в марафон бот спросит: "На сколько дней?". Выбирайте от 1 до 30 дней. Каждая новая генерация ссылки аннулирует предыдущую.
✅ <b>🎯 Безопасные Марафоны:</b> Ссылки в марафоны теперь защищены уникальными токенами. Новые приглашения будут строго по вашему таймеру.
✅ <b>🧠 Система "Штук":</b> Теперь подопечным проще вести дневник — они могут писать еду в штуках, а бот сам предложит вес. Меньше трудностей — выше доводимость до результата!

✅ <b>💎 Профессиональный рост:</b> Мы выходим на новый уровень. Система тарифов позволит нам внедрять еще более мощные AI-инструменты для вашей работы. Ваши текущие ученики получат <b>месяц PRO в подарок</b> после релиза.

🌟 <b>Вместе мы создаем нечто большее, чем просто бот.</b> Спасибо за вашу экспертизу!

<i>Работаем на результат! 🦾🌶️</i>"""

async def send_msg(bot, user_id, text):
    if DRY_RUN:
        logger.info(f"[DRY RUN] Would send to {user_id}")
        return True
    
    try:
        await bot.send_message(user_id, text, parse_mode="HTML")
        return True
    except TelegramForbiddenError:
        logger.warning(f"User {user_id} blocked the bot.")
        return False
    except TelegramRetryAfter as e:
        logger.warning(f"Flood limit exceeded. Sleeping {e.retry_after}s")
        await asyncio.sleep(e.retry_after)
        return await send_msg(bot, user_id, text) # Retry once
    except Exception as e:
        logger.error(f"Failed to send to {user_id}: {e}")
        return False

async def main():
    bot = Bot(token=settings.BOT_TOKEN)
    await init_db()
    
    logger.info(f"Starting broadcast (DRY_RUN={DRY_RUN}, TEST_MODE={TEST_MODE})...")
    
    stats = {"total": 0, "success": 0, "blocked": 0, "failed": 0, "curators": 0}
    
    async for session in get_db():
        stmt = select(User)
        if TEST_MODE:
            stmt = stmt.where(User.id.in_(TEST_USER_IDS))
            
        result = await session.execute(stmt)
        users = result.scalars().all()
        stats["total"] = len(users)
        
        for user in users:
            text = USER_MESSAGE
            if user.role in ["curator", "admin"]:
                text += "\n\n" + CURATOR_MESSAGE_ADDON
                stats["curators"] += 1
            
            if await send_msg(bot, user.id, text):
                stats["success"] += 1
            else:
                stats["blocked"] += 1 # Simplified check
            
            await asyncio.sleep(0.05) # Rate limit protection
            
    logger.info(f"Finished. Stats: {stats}")
    await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
