"""Награда активным пользователям (апрель 2026).

Отправляет личное сообщение от Игоря + продлевает PRO на 7 дней
всем кто зарегистрировался 16-26.04 и залогировал хоть раз.

Запуск:
    venv/bin/python scripts/reward_active_users.py [--dry-run]
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

import argparse
from aiogram import Bot
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from database.base import engine, init_db
from database.models import (
    User, Subscription, ConsumptionLog, UserFeedback,
    PAYMENT_SOURCE_TRIAL,
)

SURVEY_START = "2026-04-16"
SURVEY_END   = "2026-04-27"
REWARD_DAYS  = 7
REWARD_TAG   = "reward_active_apr26"

# Тестовые аккаунты Игоря — не награждать
SKIP_USER_IDS = {432823154, 8524393187}


def _build_message(first_name: str, logs: int, days: int) -> str:
    name = first_name or "друг"

    if days >= 3 or logs >= 15:
        # Power user
        return (
            f"Привет, {name}! 💚\n\n"
            f"Смотрел статистику — и увидел тебя.\n\n"
            f"За последние дни ты сделала <b>{logs} записей</b> — {days} {'день' if days == 1 else 'дня' if days < 5 else 'дней'} подряд. "
            f"Это не «попробовала» — это реальная работа над собой.\n\n"
            f"FoodFlow совсем молодой, и каждый кто верит с самого начала — особенный для меня.\n\n"
            f"Дарю тебе <b>7 дней PRO</b> — просто потому что ты пользуешься, и я это вижу. 🎁\n\n"
            f"— Игорь, создатель FoodFlow"
        )
    elif logs >= 3:
        # Tried a few times
        return (
            f"Привет, {name}! 💚\n\n"
            f"Ты зарегистрировалась и записала <b>{logs} приёма пищи</b> — и это уже больше, чем большинство.\n\n"
            f"FoodFlow новый, и мне важно знать что работает и что нет. "
            f"Спасибо что дала шанс.\n\n"
            f"Дарю <b>7 дней PRO</b> — попробуй ещё раз, уже без спешки. "
            f"Если что-то непонятно — просто напиши мне сюда. 🎁\n\n"
            f"— Игорь, создатель FoodFlow"
        )
    else:
        # One log
        return (
            f"Привет, {name}! 💚\n\n"
            f"Ты попробовала FoodFlow — и это уже шаг.\n\n"
            f"Продукт совсем свежий, мне важен каждый отклик. "
            f"Дарю тебе <b>7 дней PRO</b> в знак уважения — "
            f"попробуй записать несколько дней подряд, почувствуй разницу. 🎁\n\n"
            f"Если что-то не так или хочешь написать мне напрямую — я здесь.\n\n"
            f"— Игорь, создатель FoodFlow"
        )


async def run(dry_run: bool):
    bot_token = os.environ.get("BOT_TOKEN")
    if not bot_token:
        print("❌ BOT_TOKEN не найден"); sys.exit(1)

    await init_db()
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with async_session() as session:
        # Пользователи периода с логами
        rows = (await session.execute(
            select(
                User,
                func.count(ConsumptionLog.id).label("logs"),
                func.count(func.distinct(
                    func.date(ConsumptionLog.date)
                )).label("days"),
            )
            .join(ConsumptionLog, ConsumptionLog.user_id == User.id)
            .where(User.created_at >= SURVEY_START, User.created_at < SURVEY_END)
            .group_by(User.id)
        )).all()

        # Исключить уже награждённых
        already_rewarded = {r[0] for r in (await session.execute(
            select(UserFeedback.user_id).where(UserFeedback.feedback_type == REWARD_TAG)
        )).fetchall()}

        # Исключить заблокировавших
        blocked = {r[0] for r in (await session.execute(
            select(UserFeedback.user_id).where(UserFeedback.feedback_type == "blocked")
        )).fetchall()}

        targets = [(u, logs, days) for u, logs, days in rows
                   if u.id not in already_rewarded and u.id not in blocked
                   and u.id not in SKIP_USER_IDS]

    print(f"\n{'='*55}")
    print(f"🎁 Активных к награде: {len(targets)} чел.")
    print(f"   dry_run: {dry_run}")
    print(f"{'='*55}\n")

    if dry_run:
        for u, logs, days in targets:
            print(f"  {(u.first_name or '?'):25s}  logs={logs}  days={days}")
        return

    bot = Bot(token=bot_token)
    now = datetime.now()

    async with async_session() as session:
        for user, logs, days in targets:
            msg = _build_message(user.first_name, logs, days)
            try:
                await bot.send_message(
                    chat_id=user.id,
                    text=msg,
                    parse_mode="HTML",
                )

                # Продлеваем PRO на 7 дней
                sub = (await session.execute(
                    select(Subscription).where(Subscription.user_id == user.id)
                )).scalar_one_or_none()

                if sub:
                    base = max(sub.expires_at or now, now)
                    sub.expires_at = base + timedelta(days=REWARD_DAYS)
                    sub.tier = "pro"
                    sub.is_active = True
                    if sub.payment_source not in ("stars", "yookassa"):
                        sub.payment_source = PAYMENT_SOURCE_TRIAL
                else:
                    sub = Subscription(
                        user_id=user.id,
                        tier="pro",
                        starts_at=now,
                        expires_at=now + timedelta(days=REWARD_DAYS),
                        is_active=True,
                        payment_source=PAYMENT_SOURCE_TRIAL,
                    )
                    session.add(sub)

                # Помечаем что наградили
                session.add(UserFeedback(
                    user_id=user.id,
                    feedback_type=REWARD_TAG,
                    answer=f"logs={logs},days={days}",
                ))
                await session.commit()

                exp = sub.expires_at.strftime("%d.%m.%Y") if sub.expires_at else "∞"
                print(f"  ✅ {(user.first_name or '?'):25s}  PRO до {exp}")

            except Exception as e:
                print(f"  ❌ {(user.first_name or '?'):25s}  {e}")
            await asyncio.sleep(0.15)

    await bot.session.close()
    print(f"\n✅ Готово!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(dry_run=args.dry_run))
