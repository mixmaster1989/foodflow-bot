import asyncio
from aiogram import Bot

async def send():
    token = "8587231248:AAFFX3Q3FNySIL_RsJbLUzweGPuZQHXnAYE"
    bot = Bot(token=token)
    try:
        await bot.send_message(
            142190129, 
            "👋 <b>Илья, прошу прощения за заминку!</b>\n\n"
            "Мы только что обновили систему. Пожалуйста, нажмите <b>/start</b> еще раз, чтобы активировать бонусный PRO-доступ! 🎁🚀", 
            parse_mode="HTML"
        )
        print("✅ Сообщение Илье отправлено!")
    except Exception as e:
        print(f"❌ Ошибка при отправке: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(send())
