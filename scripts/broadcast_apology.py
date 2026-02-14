
import asyncio
import logging
import sys
import os

# Ensure project root is in path
sys.path.append(os.getcwd())

from aiogram import Bot
from sqlalchemy import select
from database.base import async_session
from database.models import User
from config import settings

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MESSAGE = """<b>📢 Техническое уведомление</b>

Уважаемые пользователи!

Сегодня произошел кратковременный технический сбой, в результате которого сервис мог быть недоступен. Приносим искренние извинения за доставленные неудобства.

✅ <b>Основной функционал полностью восстановлен.</b>
🛠 Мы продолжаем плановые работы по оптимизации стабильности системы.

Благодарим вас за терпение и понимание.

<i>Команда FoodFlow</i>"""

async def broadcast():
    print("Initializing bot...")
    # Safe init for aiogram 2.x and simple usage in 3.x for send_message
    bot = Bot(token=settings.BOT_TOKEN)
    
    print("Fetching users...")
    async with async_session() as session:
        result = await session.execute(select(User.id))
        user_ids = result.scalars().all()
    
    print(f"Target audience: {len(user_ids)} users.")
    
    sent_count = 0
    err_count = 0
    
    for user_id in user_ids:
        try:
            await bot.send_message(user_id, MESSAGE, parse_mode="HTML")
            sent_count += 1
            # Small delay to respect limits
            await asyncio.sleep(0.05)
        except Exception as e:
            logger.error(f"Failed to send to {user_id}: {e}")
            err_count += 1
            
    print(f"✅ Broadcast complete.")
    print(f"Sent: {sent_count}")
    print(f"Errors: {err_count}")
    
    await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(broadcast())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Critical error: {e}")
