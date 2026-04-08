import asyncio
import os
import sys

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.base import init_db
from services.reports import generate_admin_daily_digest

async def test_digest():
    await init_db()
    print("⏳ Генерирую админ-дайджест за вчера...")
    try:
        report = await generate_admin_daily_digest()
        print("\n--- REPORT START ---")
        print(report)
        print("--- REPORT END ---\n")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_digest())
