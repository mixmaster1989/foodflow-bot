import asyncio
from aiogram import Bot
from config import settings

async def main():
    bot = Bot(token=settings.BOT_TOKEN)
    print(f"Has get_my_star_balance: {hasattr(bot, 'get_my_star_balance')}")
    await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
