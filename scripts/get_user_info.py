import asyncio
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiogram import Bot
from config import settings

async def main():
    bot = Bot(token=settings.BOT_TOKEN)
    try:
        user_id = 295543071
        print(f"Fetching info for ID: {user_id}...")
        chat = await bot.get_chat(user_id)
        
        username = chat.username
        full_name = chat.full_name
        
        print(f"FOUND: Name='{full_name}', Username='@{username}'")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
