import asyncio
import sqlite3
import logging
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from config import settings

logging.basicConfig(level=logging.INFO)
bot = Bot(token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))


TEXT_PART_1 = """💎 <b>Добро пожаловать в семью FoodFlow!</b>

Команда проекта сердечно приветствует каждого, кто присоединился к нам в эти знаковые дни. Мы создаем не просто счетчик калорий, а умного спутника для вашей яркой и здоровой жизни. И нам безумно приятно, что вы с нами с самого старта!

✨ <b>Вы — наши ПИОНЕРЫ!</b>

Поздравляем! Вы вошли в первую сотню пользователей и официально получили статус <b>«Пионер FoodFlow»</b>. Что это значит?

🔹 <b>Приоритет навсегда:</b> при распределении будущих акций, бонусов и привилегий ваш статус будет иметь решающее значение.
🔹 <b>Голос в разработке:</b> именно вы первыми будете тестировать инновационные функции, которые изменят индустрию питания.
🔹 <b>Особое отношение:</b> вы — фундамент нашего проекта, и мы сделаем всё, чтобы ваш опыт был исключительным."""

TEXT_PART_2 = """🌱 <b>Мы растем вместе</b>

FoodFlow — молодой проект. Мы стремимся к совершенству, но на пути могут возникать «шероховатости». Если у вас возник вопрос или вы нашли баг — не пугайтесь, мы рядом!

📢 <b>Будьте в курсе и на связи:</b>

Присоединяйтесь к нашему официальному каналу:
👉 <b>https://t.me/FoodFlow2026</b>

Там мы делимся новостями, лайфхаками и отвечаем на ваши вопросы. Пишите всё, что думаете, в обсуждениях под любым постом — мы читаем каждое сообщение и ценим вашу обратную связь.

Спасибо, что доверили нам свой рацион. Впереди — только лучшее!

🍏 <i>С любовью, команда FoodFlow.</i>"""

from aiogram.types import FSInputFile
IMAGE_PATH = "/home/user1/.gemini/antigravity/brain/e93a5828-1fda-45de-951f-5d6245149dfe/pioneer_welcome_art_1774074412128.png"

async def broadcast():
    conn = sqlite3.connect('/home/user1/foodflow-bot_new/foodflow.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users")
    users = cursor.fetchall()
    
    photo = FSInputFile(IMAGE_PATH)
    
    success_count = 0
    fail_count = 0
    
    for (user_id,) in users:
        try:
             await bot.send_photo(chat_id=user_id, photo=photo, caption=TEXT_PART_1)
             await bot.send_message(chat_id=user_id, text=TEXT_PART_2)
             success_count += 1
             logging.info(f"Sent to {user_id}")
             await asyncio.sleep(0.1) # anti-spam buffer
        except Exception as e:
             logging.error(f"Failed for {user_id}: {e}")
             fail_count += 1
             
    print(f"Broadcast complete: {success_count} success, {fail_count} failed")
    await bot.session.close()

if __name__ == "__main__":
    asyncio.run(broadcast())
