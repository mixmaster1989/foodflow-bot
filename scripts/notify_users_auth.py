import asyncio
import logging
import sys
from pathlib import Path

# Add root directory to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from aiogram import Bot
from sqlalchemy.future import select

from config import settings
from database.base import get_db, init_db
from database.models import User

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def notify_users():
    bot = Bot(token=settings.BOT_TOKEN)

    # Init DB
    await init_db()

    logger.info("Starting notification script...")

    async for session in get_db():
        stmt = select(User)
        result = await session.execute(stmt)
        users = result.scalars().all()

        logger.info(f"Found {len(users)} users to notify.")

        for user in users:
            # Generate password
            password = f"MYSELF{user.id}"

            try:
                await bot.send_message(
                    chat_id=user.id,
                    text=(
                        "🚧 <b>Внимание: Обновление безопасности</b>\n\n"
                        "Мы переходим к этапу активного тестирования, и доступ к боту теперь ограничен.\n\n"
                        f"🔒 <b>Ваш персональный пароль:</b> <code>{password}</code>\n\n"
                        "Отправьте этот пароль боту <b>одним сообщением</b>, чтобы продолжить работу.\n"
                        "Это нужно сделать только один раз."
                    ),
                    parse_mode="HTML"
                )
                logger.info(f"Notified user {user.id}")
                await asyncio.sleep(0.1) # Rate limit
            except Exception as e:
                logger.error(f"Failed to notify user {user.id}: {e}")

    await bot.session.close()
    logger.info("Notification finished.")

if __name__ == "__main__":
    asyncio.run(notify_users())
