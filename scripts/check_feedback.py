import asyncio
import os
import sys

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from database.base import init_db, get_db
from database.models import UserFeedback, User

async def check_feedback():
    await init_db()
    async for session in get_db():
        stmt = select(UserFeedback, User).join(User, UserFeedback.user_id == User.id).order_by(UserFeedback.created_at.desc())
        results = (await session.execute(stmt)).all()
        
        if not results:
            print("📭 Пока ответов нет.")
            return

        print(f"📥 Всего получено ответов: {len(results)}\n")
        print(f"{'Дата':<20} | {'Имя':<15} | {'Причина'}")
        print("-" * 60)
        for fb, user in results:
            fb_obj = fb # fb is the UserFeedback object from the tuple
            name = user.first_name or user.username or f"ID:{user.id}"
            date_str = fb_obj.created_at.strftime("%Y-%m-%d %H:%M")
            print(f"{date_str:<20} | {name[:15]:<15} | {fb_obj.answer}")

if __name__ == "__main__":
    asyncio.run(check_feedback())
