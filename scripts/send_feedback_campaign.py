import asyncio
import os
import sys
import logging
from aiogram import Bot, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, func, and_

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings
from database.base import init_db, get_db
from database.models import User, Subscription, ConsumptionLog

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("feedback_campaign")

async def run_campaign():
    await init_db()
    bot = Bot(token=settings.BOT_TOKEN)
    
    targets = []
    
    async for session in get_db():
        # Query for users who:
        # 1. Are on 'free' tier
        # 2. Joined after launch campaign (is_founding_member=0)
        # 3. Have 0 consumption logs
        # 4. (Optional) joined more than 2 days ago to avoid spamming just-joined users
        
        stmt = (
            select(User.id)
            .join(Subscription, User.id == Subscription.user_id)
            .outerjoin(ConsumptionLog, User.id == ConsumptionLog.user_id)
            .where(
                and_(
                    Subscription.tier == "free",
                    User.is_founding_member == False,
                )
            )
            .group_by(User.id)
            .having(func.count(ConsumptionLog.id) == 0)
        )
        
        result = await session.execute(stmt)
        targets = [row[0] for row in result.fetchall()]
        break

    if not targets:
        print("📭 No target users found for this campaign.")
        await bot.session.close()
        return

    print(f"🚀 Starting feedback campaign for {len(targets)} users...")
    
    builder = InlineKeyboardBuilder()
    options = [
        ("⏳ Нет времени вести дневник", "poll_fb:no_time"),
        ("🤯 Сложно разобраться", "poll_fb:too_complex"),
        ("💰 Дорого / Не хочу платить", "poll_fb:too_expensive"),
        ("🤖 Пользуюсь другим сервисом", "poll_fb:another_app"),
        ("🤷 Просто забыл(а)", "poll_fb:just_forgot")
    ]
    for text, data in options:
        builder.button(text=text, callback_data=data)
    builder.adjust(1)
    
    msg_text = (
        "🎁 <b>Мы скучаем по тебе в FoodFlow!</b>\n\n"
        "Заметили, что ты перестал заглядывать к нам. Нам очень важно понять: что пошло не так?\n\n"
        "Пройди короткий опрос (1 клик) и мы подарим тебе <b>еще 3 дня PRO-статуса</b> в благодарность за помощь! 👇"
    )

    success_count = 0
    for uid in targets:
        try:
            await bot.send_message(
                chat_id=uid,
                text=msg_text,
                reply_markup=builder.as_markup(),
                parse_mode="HTML"
            )
            success_count += 1
            print(f"✅ Sent to {uid}")
            await asyncio.sleep(0.1) # Rate limiting
        except Exception as e:
            print(f"❌ Failed for {uid}: {e}")

    print(f"📊 Campaign finished! Sent: {success_count}/{len(targets)}")
    await bot.session.close()

if __name__ == "__main__":
    asyncio.run(run_campaign())
