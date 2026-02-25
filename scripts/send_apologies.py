import asyncio
from aiogram import Bot
from config import settings

async def send_apologies():
    bot = Bot(token=settings.BOT_TOKEN)
    
    # List of affected user IDs
    user_ids = [
        109153550,   # Elena Vasilieva
        1958422723,  # Оларь Андрей
        8560434937,  # Елена
        1044916834,  # Ксюша Ермолаева
        1020860110,  # Владимир Гавва 💎
        104202119    # Вера Писковацкова
    ]
    
    text = (
        "❤️ <b>Просим прощения!</b>\n\n"
        "Из-за технического обновления системы ваши настройки профиля (цели и личные данные) могли сброситься. 😔\n\n"
        "Пожалуйста, нажмите на кнопку <b>'🏠 Главное меню'</b> или введите каманду <b>/start</b>, "
        "чтобы заново пройти быструю настройку. Это займет всего минуту!\n\n"
        "Мы уже всё починили, чтобы это не повторилось. Спасибо, что вы с нами! 🙏"
    )
    
    print(f"Starting apology broadcast to {len(user_ids)} users...")
    
    for user_id in user_ids:
        try:
            await bot.send_message(user_id, text, parse_mode="HTML")
            print(f"✅ Sent to {user_id}")
            await asyncio.sleep(0.1) # Be gentle
        except Exception as e:
            print(f"❌ Failed for {user_id}: {e}")
            
    await bot.session.close()
    print("Done.")

if __name__ == "__main__":
    asyncio.run(send_apologies())
