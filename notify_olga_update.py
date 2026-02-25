import asyncio

from aiogram import Bot

from config import settings

OLGA_ID = 295543071

async def send_notification():
    bot = Bot(token=settings.BOT_TOKEN)

    text = (
        "🚀 <b>Обновление FoodFlow!</b>\n\n"
        "Ольга, теперь пользоваться ботом стало ещё проще!\n\n"
        "📝 <b>Просто пишите еду в чат.</b>\n"
        "Больше не нужно искать кнопки в меню. Просто отправьте боту сообщение с названием продукта, например:\n"
        "• <i>Борщ 300г</i>\n"
        "• <i>Яблоко</i>\n"
        "• <i>Творог 5% 200 грамм</i>\n\n"
        "Бот сам поймет и спросит, что сделать: <b>«Я съел»</b> или <b>«В холодильник»</b>.\n\n"
        "💡 <b>Важные советы:</b>\n"
        "1. <b>Указывайте вес.</b> Чем точнее вы напишете (например, <code>200г</code>, <code>300мл</code> или <code>1 шт</code>), тем точнее нейросеть посчитает калории.\n"
        "2. <b>Уточняйте детали.</b> <i>«Кофе с молоком и сахаром»</i> посчитается гораздо точнее, чем просто <i>«Кофе»</i>.\n"
        "3. <b>Если вес не указан</b>, бот по умолчанию посчитает порцию как <b>100г</b>.\n\n"
        "Попробуйте отправить что-нибудь прямо сейчас! 😉"
    )

    try:
        await bot.send_message(OLGA_ID, text, parse_mode="HTML")
        print(f"✅ Notification sent to Olga ({OLGA_ID})")
    except Exception as e:
        print(f"❌ Error sending notification: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(send_notification())
