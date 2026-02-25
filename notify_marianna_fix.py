import asyncio

from aiogram import Bot

from config import settings

USER_ID = 7587440056

async def send_apology():
    bot = Bot(token=settings.BOT_TOKEN)

    text = (
        "🌹 <b>Марианна, здравствуйте!</b>\n\n"
        "Несколько минут назад вы столкнулись с ошибкой в боте, когда нажимали «Я съела». "
        "Мы заметили это и сразу всё починили! 🛠️\n\n"
        "<b>Что произошло?</b>\n"
        "Бот немного растерялся, когда получил от вас фото (или стикер) вместо текста в этом меню. "
        "Теперь мы научили его вежливо просить текстовое описание, если он чего-то не понял, а не падать в обморок. 😅\n\n"
        "🙏 <b>Спасибо вам огромное!</b>\n"
        "Благодаря вашей активности мы нашли и исправили эту недоработку. Вы помогаете делать FoodFlow лучше!\n\n"
        "Желаем вам чудесного дня, вкусной (и полезной!) еды и отличного настроения! ☀️🍓"
    )

    try:
        await bot.send_message(USER_ID, text, parse_mode="HTML")
        print(f"✅ Apology sent to Marianna ({USER_ID})")
    except Exception as e:
        print(f"❌ Error sending apology: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(send_apology())
