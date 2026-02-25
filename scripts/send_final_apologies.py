import asyncio
import os
import sys

sys.path.insert(0, os.getcwd())

from aiogram import Bot

from config import settings


async def send_final_apologies():
    bot = Bot(token=settings.BOT_TOKEN)

    # 5 Users (Elena Vasilieva EXCLUDED)
    user_ids = [
        1958422723,  # Оларь Андрей
        8560434937,  # Елена
        1044916834,  # Ксюша Ермолаева
        1020860110,  # Владимир Гавва 💎
        104202119    # Вера Писковацкова
    ]

    text = (
        "🤖 <b>Важное сообщение от разработчиков</b>\n\n"
        "Друзья, мы нашли причину, почему ваши настройки могли сбрасываться. "
        "Оказалось, бот по ошибке сохранял ваш профиль 'не туда'. 🤦‍♂️\n\n"
        "🛠 <b>Сейчас ошибка полностью исправлена.</b>\n"
        "Мы переписали механизм сохранения, и теперь ваши данные точно будут в безопасности.\n\n"
        "Пожалуйста, потратьте одну минуту и пройдите настройку в последний раз (нажмите <b>/start</b> или кнопку меню). "
        "Больше это не повторится. Честное цифровое! 🤞✨\n\n"
        "<i>Спасибо за ваше терпение!</i> ❤️"
    )

    print(f"Sending final apologies to {len(user_ids)} users...")

    for user_id in user_ids:
        try:
            await bot.send_message(user_id, text, parse_mode="HTML")
            print(f"✅ Sent to {user_id}")
            await asyncio.sleep(0.1)
        except Exception as e:
            print(f"❌ Failed for {user_id}: {e}")

    await bot.session.close()
    print("Done.")

if __name__ == "__main__":
    asyncio.run(send_final_apologies())
