import asyncio
import logging
import os
import sys

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiogram import Bot
from sqlalchemy import select

from config import settings
from database.base import async_session
from database.models import User

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

USERS_TO_UNLOCK = [
    {"id": 7587440056, "name": "Марианна", "full_name": "Марианна Арзуманян"},
    {"id": 295543071, "name": "Ольга", "full_name": "Ольга Антакова"}
]

WELCOME_MESSAGE = (
    "Здравствуйте, {name}! 🌹\n\n"
    "Прошу прощения, что не сразу открыл доступ — я работал в закрытом режиме.\n"
    "Теперь всё готово! Добро пожаловать в FoodFlow! 🥗\n\n"
    "Нажмите /start, чтобы начать."
)

async def main():
    print("Starting manual access grant process...")

    # 1. Update Database
    async with async_session() as session:
        for user_data in USERS_TO_UNLOCK:
            user_id = user_data["id"]

            # Check if user exists
            stmt = select(User).where(User.id == user_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if user:
                print(f"User {user_id} exists. Updating is_verified=True...")
                user.is_verified = True
            else:
                print(f"User {user_id} not found. Creating new verified record...")
                # We don't have their username, so we'll use a placeholder or None
                new_user = User(
                    id=user_id,
                    username=f"restored_{user_id}", # Placeholder
                    is_verified=True
                )
                session.add(new_user)

        await session.commit()
        print("Database updated successfully.")

    # 2. Send Messages
    bot = Bot(token=settings.BOT_TOKEN)
    try:
        for user_data in USERS_TO_UNLOCK:
            try:
                text = WELCOME_MESSAGE.format(name=user_data["name"])
                await bot.send_message(chat_id=user_data["id"], text=text)
                print(f"Message sent to {user_data['full_name']} ({user_data['id']})")
            except Exception as e:
                print(f"Failed to send message to {user_data['full_name']}: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
