"""Рассылка продуктового опроса (апрель 2026).

Два сегмента:
  - sv1 (no_log):  зарегистрировались 16-26.04, прошли онбординг, 0 логов, не заблокировали
  - sv2 (churned): залогировали хоть раз, последний лог > 2 дней назад, не заблокировали

Запуск:
    cd /home/user1/foodflow-bot_new
    venv/bin/python scripts/send_product_survey.py

Флаги:
    --dry-run   только показать список без отправки
    --segment   sv1 | sv2 | all (по умолчанию all)
"""
import asyncio
import os
import sys
import argparse
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from database.base import engine, init_db
from database.models import User, UserSettings, UserFeedback, ConsumptionLog, Base

SURVEY_START = "2026-04-16"
SURVEY_END   = "2026-04-27"

MSG_SV1 = (
    "Привет! Меня зовут Игорь, я создаю FoodFlow.\n\n"
    "Ты зарегистрировался {days_ago} — но так и не попробовал записать, что ел. "
    "Это нормально, но мне важно понять почему.\n\n"
    "<b>Одним нажатием: что тебя остановило?</b>"
)

MSG_SV2 = (
    "Привет! Меня зовут Игорь, я создаю FoodFlow.\n\n"
    "Ты попробовал вести дневник питания — и остановился. "
    "Буду честен: мне важнее услышать правду, чем промолчать.\n\n"
    "<b>Что тебя остановило продолжить?</b>"
)

KB_SV1 = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="💭 Не понял как пользоваться",    callback_data="sv1:no_understand")],
    [InlineKeyboardButton(text="😴 Лень / казалось сложно",       callback_data="sv1:too_hard")],
    [InlineKeyboardButton(text="🔔 Просто забыл",                  callback_data="sv1:forgot")],
    [InlineKeyboardButton(text="🤷 Попробовал, не увидел смысла", callback_data="sv1:no_value")],
    [InlineKeyboardButton(text="⏰ Занят, вернусь позже",          callback_data="sv1:busy")],
])

KB_SV2 = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📉 Не увидел пользы / результата", callback_data="sv2:no_result")],
    [InlineKeyboardButton(text="😐 Скучно / рутинно",              callback_data="sv2:too_boring")],
    [InlineKeyboardButton(text="😓 Сложно, много усилий",          callback_data="sv2:too_hard")],
    [InlineKeyboardButton(text="🔔 Просто забыл",                  callback_data="sv2:forgot")],
    [InlineKeyboardButton(text="📱 Нашёл другой способ",           callback_data="sv2:other_app")],
])


def _days_ago_label(registered_at: datetime) -> str:
    days = (datetime.now() - registered_at).days
    if days == 0:   return "сегодня"
    if days == 1:   return "вчера"
    if days < 7:    return f"{days} дня назад" if days < 5 else f"{days} дней назад"
    return f"на прошлой неделе"


async def get_segments(session: AsyncSession):
    # Общий фильтр: зарегистрированы в окне
    new_user_filter = and_(
        User.created_at >= SURVEY_START,
        User.created_at < SURVEY_END,
    )

    # Уже получившие этот опрос
    sent_sv1_ids = {r[0] for r in (await session.execute(
        select(UserFeedback.user_id).where(UserFeedback.feedback_type.in_(["survey_v1_sent", "survey_1"]))
    )).fetchall()}
    sent_sv2_ids = {r[0] for r in (await session.execute(
        select(UserFeedback.user_id).where(UserFeedback.feedback_type.in_(["survey_v2_sent", "survey_2"]))
    )).fetchall()}

    # Заблокировавшие
    blocked_ids = {r[0] for r in (await session.execute(
        select(UserFeedback.user_id).where(UserFeedback.feedback_type == "blocked")
    )).fetchall()}

    # Сегмент sv1: онбординг есть, 0 логов
    all_new = (await session.execute(
        select(User).where(new_user_filter)
    )).scalars().all()

    sv1, sv2 = [], []

    for user in all_new:
        if user.id in blocked_ids:
            continue

        has_settings = (await session.execute(
            select(func.count(UserSettings.user_id)).where(
                and_(UserSettings.user_id == user.id, UserSettings.is_initialized == True)
            )
        )).scalar() or 0

        if not has_settings:
            continue

        log_count = (await session.execute(
            select(func.count(ConsumptionLog.id)).where(ConsumptionLog.user_id == user.id)
        )).scalar() or 0

        if log_count == 0:
            if user.id not in sent_sv1_ids:
                sv1.append(user)
        else:
            # sv2: залогировали, но последний лог > 2 дней назад
            last_log_date = (await session.execute(
                select(func.max(ConsumptionLog.date)).where(ConsumptionLog.user_id == user.id)
            )).scalar()
            if last_log_date and (datetime.now() - last_log_date).total_seconds() > 48 * 3600:
                if user.id not in sent_sv2_ids:
                    sv2.append(user)

    return sv1, sv2


async def mark_sent(session: AsyncSession, user_id: int, survey_type: str):
    """Записываем что опрос отправлен — чтобы не слать повторно."""
    session.add(UserFeedback(
        user_id=user_id,
        feedback_type=f"survey_v{survey_type}_sent",
        answer="sent",
    ))
    await session.commit()


async def run(dry_run: bool, segment: str):
    bot_token = os.environ.get("BOT_TOKEN")
    if not bot_token:
        print("❌ BOT_TOKEN не найден")
        sys.exit(1)

    await init_db()
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with async_session() as session:
        sv1_users, sv2_users = await get_segments(session)

    print(f"\n{'='*50}")
    print(f"📊 Сегменты:")
    print(f"  sv1 (0 логов):   {len(sv1_users)} чел.")
    print(f"  sv2 (ушли):      {len(sv2_users)} чел.")
    print(f"  dry_run:         {dry_run}")
    print(f"{'='*50}\n")

    if dry_run:
        print("sv1 (no_log):")
        for u in sv1_users:
            print(f"  {u.first_name or '?':25s}  id={u.id}  reg={u.created_at.strftime('%d.%m') if u.created_at else '?'}")
        print("\nsv2 (churned):")
        for u in sv2_users:
            print(f"  {u.first_name or '?':25s}  id={u.id}  reg={u.created_at.strftime('%d.%m') if u.created_at else '?'}")
        return

    bot = Bot(token=bot_token)
    sent_ok = 0
    errors = 0

    async with async_session() as session:
        if segment in ("sv1", "all"):
            print(f"📤 Отправляю sv1 ({len(sv1_users)} чел)...")
            for user in sv1_users:
                days_ago = _days_ago_label(user.created_at) if user.created_at else "недавно"
                text = MSG_SV1.format(days_ago=days_ago)
                try:
                    await bot.send_message(
                        chat_id=user.id,
                        text=text,
                        reply_markup=KB_SV1,
                        parse_mode="HTML",
                    )
                    await mark_sent(session, user.id, "1")
                    print(f"  ✅ {user.first_name or user.id}")
                    sent_ok += 1
                except Exception as e:
                    print(f"  ❌ {user.first_name or user.id}: {e}")
                    errors += 1
                await asyncio.sleep(0.15)  # Telegram rate limit

        if segment in ("sv2", "all"):
            print(f"\n📤 Отправляю sv2 ({len(sv2_users)} чел)...")
            for user in sv2_users:
                try:
                    await bot.send_message(
                        chat_id=user.id,
                        text=MSG_SV2,
                        reply_markup=KB_SV2,
                        parse_mode="HTML",
                    )
                    await mark_sent(session, user.id, "2")
                    print(f"  ✅ {user.first_name or user.id}")
                    sent_ok += 1
                except Exception as e:
                    print(f"  ❌ {user.first_name or user.id}: {e}")
                    errors += 1
                await asyncio.sleep(0.15)

    await bot.session.close()
    print(f"\n{'='*50}")
    print(f"✅ Отправлено: {sent_ok}")
    print(f"❌ Ошибок:    {errors}")
    print(f"{'='*50}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Показать список без отправки")
    parser.add_argument("--segment", choices=["sv1", "sv2", "all"], default="all")
    args = parser.parse_args()
    asyncio.run(run(dry_run=args.dry_run, segment=args.segment))
