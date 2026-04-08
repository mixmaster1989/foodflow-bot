import asyncio
import os
import sys
from aiogram import Bot, types
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings

async def send_test_poll():
    bot = Bot(token=settings.BOT_TOKEN)
    admin_id = settings.ADMIN_IDS[0] # 432823154
    
    print(f"🚀 Sending test poll to admin: {admin_id}")
    
    builder = InlineKeyboardBuilder()
    # Варианты ответов для тех, кто забросил бота
    options = [
        ("⏳ Нет времени вести дневник", "poll_fb:no_time"),
        ("🤯 Сложно разобраться", "poll_fb:too_complex"),
        ("💰 Дорого / Не хочу платить", "poll_fb:too_expensive"),
        ("🤖 Пользуюсь другим сервисом", "poll_fb:another_app"),
        ("🤷 Просто забыл(а)", "poll_fb:just_forgot")
    ]
    
    for text, data in options:
        builder.button(text=text, callback_data=data)
    
    builder.adjust(1)
    
    text = (
        "🎁 **Мы скучаем по тебе в FoodFlow!**\n\n"
        "Заметили, что ты перестал заглядывать к нам. Нам очень важно понять: что пошло не так?\n\n"
        "Пройди короткий опрос (1 клик) и мы подарим тебе **еще 3 дня PRO-статуса** в благодарность за честность! 👇"
    )
    
    try:
        await bot.send_message(
            chat_id=admin_id,
            text=text,
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )
        print("✅ Message sent successfully!")
    except Exception as e:
        print(f"❌ Failed to send message: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(send_test_poll())
