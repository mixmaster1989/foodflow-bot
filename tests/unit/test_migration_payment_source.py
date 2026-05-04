"""Тест миграции payment_source — backfill исторических записей.

Проверяет 4-step backfill в database/migrations.py:
1. telegram_payment_charge_id IS NOT NULL → 'stars'
2. user_id ∈ referral_rewards.is_active=1 → 'referral'
3. user_id ∈ user_feedback (poll) → 'feedback_bonus'
4. остальные tier!=free → 'trial'
5. tier='free' остаётся NULL
6. уже выставленный source — не трогать (идемпотентность)
"""
import os
import sqlite3
import tempfile
from unittest.mock import patch

import pytest


def _create_legacy_schema(cursor: sqlite3.Cursor):
    """Создаёт схему БД БЕЗ колонок payment_source/yookassa_payment_id (как было до миграции)."""
    cursor.execute("""
        CREATE TABLE subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id BIGINT NOT NULL UNIQUE,
            tier TEXT DEFAULT 'free',
            starts_at DATETIME,
            expires_at DATETIME,
            is_active BOOLEAN DEFAULT 1,
            telegram_payment_charge_id TEXT,
            auto_renew BOOLEAN DEFAULT 1
        )
    """)
    cursor.execute("""
        CREATE TABLE referral_rewards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id BIGINT NOT NULL,
            reward_type TEXT NOT NULL,
            days INTEGER NOT NULL,
            source TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 0,
            created_at DATETIME,
            activated_at DATETIME
        )
    """)
    cursor.execute("""
        CREATE TABLE user_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id BIGINT NOT NULL,
            feedback_type TEXT NOT NULL,
            answer TEXT NOT NULL,
            created_at DATETIME
        )
    """)


def test_migration_backfill_classifies_existing_records():
    """4-step backfill корректно классифицирует исторические записи."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        # 1. Подготовка: legacy-схема + 6 пред-существующих записей
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        _create_legacy_schema(cur)

        # User 100: tier='free' → должен остаться NULL
        cur.execute(
            "INSERT INTO subscriptions (user_id, tier, telegram_payment_charge_id) "
            "VALUES (100, 'free', NULL)"
        )
        # User 200: real Stars-платёж → 'stars'
        cur.execute(
            "INSERT INTO subscriptions (user_id, tier, telegram_payment_charge_id) "
            "VALUES (200, 'pro', 'tg_charge_real')"
        )
        # User 300: trial без следов → 'trial'
        cur.execute(
            "INSERT INTO subscriptions (user_id, tier, telegram_payment_charge_id) "
            "VALUES (300, 'pro', NULL)"
        )
        # User 400: referral_rewards.is_active=1 → 'referral'
        cur.execute(
            "INSERT INTO subscriptions (user_id, tier, telegram_payment_charge_id) "
            "VALUES (400, 'pro', NULL)"
        )
        cur.execute(
            "INSERT INTO referral_rewards (user_id, reward_type, days, source, is_active) "
            "VALUES (400, 'pro_days', 14, 'ref_invite_paid', 1)"
        )
        # User 500: user_feedback poll → 'feedback_bonus'
        cur.execute(
            "INSERT INTO subscriptions (user_id, tier, telegram_payment_charge_id) "
            "VALUES (500, 'pro', NULL)"
        )
        cur.execute(
            "INSERT INTO user_feedback (user_id, feedback_type, answer) "
            "VALUES (500, 'inactive_poll_v1', 'still_using')"
        )
        conn.commit()
        conn.close()

        # 2. Запуск миграции с подменой DATABASE_URL
        from config import settings as cfg_settings
        original_url = cfg_settings.DATABASE_URL
        cfg_settings.DATABASE_URL = f"sqlite:///{db_path}"
        try:
            from database.migrations import _run_sqlite_migrations
            _run_sqlite_migrations()
        finally:
            cfg_settings.DATABASE_URL = original_url

        # 3. Проверка: открываем заново и читаем
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        cur.execute("PRAGMA table_info(subscriptions)")
        columns = {row[1] for row in cur.fetchall()}
        assert "payment_source" in columns
        assert "yookassa_payment_id" in columns

        rows = dict(cur.execute(
            "SELECT user_id, payment_source FROM subscriptions"
        ).fetchall())

        assert rows[100] is None, f"tier='free' должен остаться NULL, получено: {rows[100]!r}"
        assert rows[200] == "stars", f"telegram_payment_charge_id IS NOT NULL → 'stars', получено: {rows[200]!r}"
        assert rows[300] == "trial", f"trial без следов → 'trial', получено: {rows[300]!r}"
        assert rows[400] == "referral", f"referral_rewards.is_active=1 → 'referral', получено: {rows[400]!r}"
        assert rows[500] == "feedback_bonus", f"user_feedback poll → 'feedback_bonus', получено: {rows[500]!r}"

        # 4. Идемпотентность: повторный запуск не меняет ничего
        cfg_settings.DATABASE_URL = f"sqlite:///{db_path}"
        try:
            _run_sqlite_migrations()
        finally:
            cfg_settings.DATABASE_URL = original_url

        rows2 = dict(cur.execute(
            "SELECT user_id, payment_source FROM subscriptions"
        ).fetchall())
        assert rows == rows2, "Повторный запуск миграции не должен менять payment_source"

        conn.close()
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)
