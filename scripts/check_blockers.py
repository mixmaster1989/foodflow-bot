import asyncio
import os
import sys

sys.path.insert(0, os.getcwd())

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError

from config import settings


async def check_users():
    bot = Bot(token=settings.BOT_TOKEN)

    candidates = [
        (1958422723, "Оларь Андрей"),
        (8560434937, "Елена"),
        (109153550, "Елена Васильева"),
        (1044916834, "Ксюша Ермолаева"),
        (1020860110, "Владимир Гавва 💎"),
        (104202119, "Вера Писковацкова")
    ]

    active_users = []
    blocked_users = []

    print("Checking user status...")
    for user_id, name in candidates:
        try:
            # Try to send a chat action (typing) - invisible but verifies access
            await bot.send_chat_action(chat_id=user_id, action="typing")
            active_users.append((user_id, name))
            print(f"✅ Active: {name} ({user_id})")
        except TelegramForbiddenError:
            blocked_users.append((user_id, name))
            print(f"❌ BLOCKED: {name} ({user_id})")
        except Exception as e:
            print(f"⚠️ Error for {name} ({user_id}): {e}")
            # Assume active if error is not Forbidden (e.g. network)
            if "forbidden" not in str(e).lower():
                 active_users.append((user_id, name))

        await asyncio.sleep(0.2)

    print("\n--- SUMMARY ---")
    print(f"Active Users (Need Onboarding): {len(active_users)}")
    for uid, name in active_users:
        print(f"- {name} (ID: {uid})")

    await bot.session.close()

if __name__ == "__main__":
    asyncio.run(check_users())
