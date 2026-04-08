"""Marketing analytics service for FoodFlow.

Provides aggregated metrics for the marketing team:
- Daily digest
- Acquisition funnel
- Retention (DAU/WAU/MAU)
- Tier distribution
- Hourly activity heatmap
- Acquisition sources
- CSV export
"""
import csv
import io
import json
import logging
from datetime import datetime, timedelta

from sqlalchemy import and_, func, select

from database.base import get_db
from database.models import (
    ConsumptionLog,
    ReferralEvent,
    Subscription,
    User,
    UserFeedback,
    UserSettings,
)

logger = logging.getLogger(__name__)

# Price maps for revenue estimation
PRICES_RUB = {"basic": 199, "pro": 299, "curator": 499}
PRICES_STARS = {"basic": 130, "pro": 200, "curator": 350}

SOURCE_LABELS = {
    "tg_ads": "📢 Реклама в Телеграм",
    "friend": "👤 Рекомендация друга",
    "social": "📱 Соцсети",
    "search": "🔍 Поиск",
    "blogger": "🗣️ Блогер",
    "herbalife": "🌿 Herbalife",
    "other": "🔗 Другое",
}


async def get_daily_digest() -> str:
    """Compact daily digest for marketing group (plain text, no HTML tags)."""
    yesterday = (datetime.now() - timedelta(days=1)).date()
    date_str = yesterday.strftime("%d.%m.%Y")

    async for session in get_db():
        nu = (await session.execute(
            select(func.count(User.id)).where(func.date(User.created_at) == yesterday)
        )).scalar() or 0

        total = (await session.execute(select(func.count(User.id)))).scalar() or 0

        au = (await session.execute(
            select(func.count(func.distinct(ConsumptionLog.user_id))).where(
                func.date(ConsumptionLog.date) == yesterday
            )
        )).scalar() or 0

        logs = (await session.execute(
            select(func.count(ConsumptionLog.id)).where(
                func.date(ConsumptionLog.date) == yesterday
            )
        )).scalar() or 0

        ref = (await session.execute(
            select(func.count(ReferralEvent.id)).where(and_(
                func.date(ReferralEvent.created_at) == yesterday,
                ReferralEvent.event_type == "signup"
            ))
        )).scalar() or 0

        fb = (await session.execute(
            select(func.count(UserFeedback.id)).where(
                func.date(UserFeedback.created_at) == yesterday
            )
        )).scalar() or 0

        # Payments
        subs = (await session.execute(
            select(Subscription).where(and_(
                func.date(Subscription.starts_at) == yesterday,
                Subscription.tier != "free"
            ))
        )).scalars().all()

        rev_rub, rev_stars, cnt_rub, cnt_stars = 0, 0, 0, 0
        for s in subs:
            if s.telegram_payment_charge_id:
                cnt_stars += 1
                rev_stars += PRICES_STARS.get(s.tier, 0)
            else:
                cnt_rub += 1
                rev_rub += PRICES_RUB.get(s.tier, 0)

        break

    dau_pct = f"{au / total * 100:.1f}" if total else "0"

    return (
        f"📊 Маркетинг-сводка ({date_str})\n\n"
        f"👥 Юзеры: +{nu} новых (реф: {ref}) | всего: {total}\n"
        f"📈 DAU: {au} ({dau_pct}%) | логов еды: {logs}\n"
        f"💬 Фидбек: {fb}\n"
        f"💰 Продажи: {rev_rub}₽ ({cnt_rub} шт) + {rev_stars}⭐ ({cnt_stars} шт)"
    )


async def get_acquisition_funnel(days: int = 14) -> str:
    """Registration funnel for the last N days."""
    lines = [f"📊 Воронка привлечения (последние {days} дней)\n"]
    lines.append("Дата       | Новые | Реф | Онб.✅")
    lines.append("———————————|———————|—————|———————")

    async for session in get_db():
        for i in range(days):
            d = (datetime.now() - timedelta(days=i + 1)).date()

            nu = (await session.execute(
                select(func.count(User.id)).where(func.date(User.created_at) == d)
            )).scalar() or 0

            ref = (await session.execute(
                select(func.count(ReferralEvent.id)).where(and_(
                    func.date(ReferralEvent.created_at) == d,
                    ReferralEvent.event_type == "signup"
                ))
            )).scalar() or 0

            # Users who completed onboarding on this date
            onb = (await session.execute(
                select(func.count(UserSettings.id)).where(and_(
                    UserSettings.is_initialized == True,  # noqa: E712
                    func.date(User.created_at) == d
                )).join(User, User.id == UserSettings.user_id)
            )).scalar() or 0

            lines.append(f"{d.strftime('%d.%m')}     |  {nu:>3}  | {ref:>3} |  {onb:>3}")

        break

    return "\n".join(lines)


async def get_retention_metrics() -> str:
    """Calculate DAU, WAU, MAU based on food log activity."""
    now = datetime.now()
    today = now.date()

    async for session in get_db():
        total = (await session.execute(select(func.count(User.id)))).scalar() or 0

        # DAU — yesterday
        yesterday = today - timedelta(days=1)
        dau = (await session.execute(
            select(func.count(func.distinct(ConsumptionLog.user_id))).where(
                func.date(ConsumptionLog.date) == yesterday
            )
        )).scalar() or 0

        # WAU — last 7 days
        week_ago = today - timedelta(days=7)
        wau = (await session.execute(
            select(func.count(func.distinct(ConsumptionLog.user_id))).where(
                func.date(ConsumptionLog.date) >= week_ago
            )
        )).scalar() or 0

        # MAU — last 30 days
        month_ago = today - timedelta(days=30)
        mau = (await session.execute(
            select(func.count(func.distinct(ConsumptionLog.user_id))).where(
                func.date(ConsumptionLog.date) >= month_ago
            )
        )).scalar() or 0

        # Onboarding conversion
        onboarded = (await session.execute(
            select(func.count(UserSettings.id)).where(
                UserSettings.is_initialized == True  # noqa: E712
            )
        )).scalar() or 0

        break

    def pct(a, b):
        return f"{a / b * 100:.1f}%" if b else "—"

    return (
        f"📈 Удержание (Retention)\n\n"
        f"👥 Всего в базе: {total}\n"
        f"✅ Онбординг пройден: {onboarded} ({pct(onboarded, total)})\n\n"
        f"📅 DAU (вчера): {dau} ({pct(dau, total)})\n"
        f"📅 WAU (7 дней): {wau} ({pct(wau, total)})\n"
        f"📅 MAU (30 дней): {mau} ({pct(mau, total)})\n\n"
        f"🔄 Sticky factor (DAU/MAU): {pct(dau, mau)}"
    )


async def get_tier_distribution() -> str:
    """Distribution of users across subscription tiers."""
    async for session in get_db():
        total = (await session.execute(select(func.count(User.id)))).scalar() or 0

        # Active paid subscriptions
        tiers = {}
        for tier in ["basic", "pro", "curator"]:
            cnt = (await session.execute(
                select(func.count(Subscription.id)).where(and_(
                    Subscription.tier == tier,
                    Subscription.is_active == True  # noqa: E712
                ))
            )).scalar() or 0
            tiers[tier] = cnt

        paid = sum(tiers.values())
        free = total - paid

        break

    def pct(a, b):
        return f"{a / b * 100:.1f}%" if b else "—"

    return (
        f"💎 Распределение тарифов\n\n"
        f"🆓 Free: {free} ({pct(free, total)})\n"
        f"🔵 Basic: {tiers['basic']} ({pct(tiers['basic'], total)})\n"
        f"🟣 Pro: {tiers['pro']} ({pct(tiers['pro'], total)})\n"
        f"🟢 Curator: {tiers['curator']} ({pct(tiers['curator'], total)})\n\n"
        f"Всего платных: {paid} ({pct(paid, total)})"
    )


async def get_hourly_activity(days: int = 7) -> str:
    """Hourly heatmap of food logging activity."""
    since = (datetime.now() - timedelta(days=days)).date()

    async for session in get_db():
        # Get all logs since the cutoff
        logs_stmt = select(ConsumptionLog.date).where(
            func.date(ConsumptionLog.date) >= since
        )
        rows = (await session.execute(logs_stmt)).scalars().all()
        break

    # Count by hour
    hour_counts = [0] * 24
    for dt in rows:
        hour_counts[dt.hour] += 1

    max_count = max(hour_counts) if hour_counts else 1

    lines = [f"🕐 Активность по часам (последние {days} дней)\n"]
    for h in range(24):
        bar_len = int((hour_counts[h] / max_count) * 15) if max_count else 0
        bar = "█" * bar_len
        lines.append(f"{h:02d}:00  {bar} {hour_counts[h]}")

    # Find peak hour
    peak = hour_counts.index(max(hour_counts))
    lines.append(f"\n🔥 Пиковый час: {peak:02d}:00 ({max(hour_counts)} записей)")

    return "\n".join(lines)


async def get_acquisition_sources() -> str:
    """Aggregated acquisition source report from onboarding survey."""
    async for session in get_db():
        rows = (await session.execute(
            select(UserFeedback.answer, UserFeedback.created_at).where(
                UserFeedback.feedback_type == "acquisition_source"
            ).order_by(UserFeedback.created_at.desc())
        )).all()
        break

    if not rows:
        return "📋 Источники привлечения\n\nДанных пока нет. Опрос появляется у новых пользователей при онбординге."

    # Aggregate by source
    counts: dict[str, int] = {}
    for answer_json, _ in rows:
        try:
            data = json.loads(answer_json)
            key = data.get("source", "other")
        except (json.JSONDecodeError, TypeError):
            key = "other"
        counts[key] = counts.get(key, 0) + 1

    total = sum(counts.values())
    lines = [f"📋 Источники привлечения (всего ответов: {total})\n"]

    # Sort by count descending
    for key, cnt in sorted(counts.items(), key=lambda x: -x[1]):
        label = SOURCE_LABELS.get(key, key)
        pct = f"{cnt / total * 100:.0f}%" if total else "—"
        bar_len = int((cnt / max(counts.values())) * 10) if counts else 0
        bar = "█" * bar_len
        lines.append(f"{label}: {cnt} ({pct}) {bar}")

    # Last 5 respondents
    lines.append("\n🕐 Последние 5:")
    for answer_json, created_at in rows[:5]:
        try:
            d = json.loads(answer_json)
            name = d.get("first_name", "")
            uname = f"@{d['username']}" if d.get("username") else ""
            src = SOURCE_LABELS.get(d.get("source", ""), "?")
            lines.append(f"  {name} {uname} → {src}")
        except Exception:
            pass

    return "\n".join(lines)


async def export_csv(days: int = 30) -> io.BytesIO:
    """Generate CSV export for the last N days + acquisition sources."""
    output = io.StringIO()
    writer = csv.writer(output)

    # --- Sheet 1: Daily stats ---
    writer.writerow(["=== DAILY STATS ==="])
    writer.writerow([
        "Date", "New Users", "Ref Signups", "Active Users (DAU)",
        "Food Logs", "Feedback", "Sales RUB", "Rev RUB",
        "Sales Stars", "Rev Stars"
    ])

    async for session in get_db():
        for i in range(days):
            d = (datetime.now() - timedelta(days=i + 1)).date()

            nu = (await session.execute(select(func.count(User.id)).where(func.date(User.created_at) == d))).scalar() or 0
            ref = (await session.execute(select(func.count(ReferralEvent.id)).where(and_(func.date(ReferralEvent.created_at) == d, ReferralEvent.event_type == "signup")))).scalar() or 0
            au = (await session.execute(select(func.count(func.distinct(ConsumptionLog.user_id))).where(func.date(ConsumptionLog.date) == d))).scalar() or 0
            lc = (await session.execute(select(func.count(ConsumptionLog.id)).where(func.date(ConsumptionLog.date) == d))).scalar() or 0
            fc = (await session.execute(select(func.count(UserFeedback.id)).where(func.date(UserFeedback.created_at) == d))).scalar() or 0

            subs = (await session.execute(select(Subscription).where(and_(func.date(Subscription.starts_at) == d, Subscription.tier != "free")))).scalars().all()
            p_rub, p_xtr, r_rub, r_xtr = 0, 0, 0, 0
            for s in subs:
                if s.telegram_payment_charge_id:
                    p_xtr += 1
                    r_xtr += PRICES_STARS.get(s.tier, 0)
                else:
                    p_rub += 1
                    r_rub += PRICES_RUB.get(s.tier, 0)

            writer.writerow([d.strftime("%Y-%m-%d"), nu, ref, au, lc, fc, p_rub, r_rub, p_xtr, r_xtr])

        # --- Sheet 2: Acquisition sources ---
        writer.writerow([])
        writer.writerow(["=== ACQUISITION SOURCES ==="])
        writer.writerow(["Date", "User ID", "Username", "First Name", "Last Name", "Source", "Source Label"])

        src_rows = (await session.execute(
            select(UserFeedback).where(
                UserFeedback.feedback_type == "acquisition_source"
            ).order_by(UserFeedback.created_at.desc())
        )).scalars().all()

        for fb in src_rows:
            try:
                d = json.loads(fb.answer)
                writer.writerow([
                    fb.created_at.strftime("%Y-%m-%d %H:%M") if fb.created_at else "",
                    d.get("user_id", ""),
                    d.get("username", ""),
                    d.get("first_name", ""),
                    d.get("last_name", ""),
                    d.get("source", ""),
                    d.get("source_label", ""),
                ])
            except Exception:
                writer.writerow([fb.created_at, fb.user_id, "", "", "", fb.answer, ""])

        break

    output.seek(0)
    return io.BytesIO(output.getvalue().encode("utf-8"))

