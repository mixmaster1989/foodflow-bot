import asyncio
import sqlite3
from collections.abc import Iterable
from pathlib import Path

from config import settings


def _get_sqlite_path() -> Path | None:
    if not settings.DATABASE_URL.startswith("sqlite"):
        return None
    # sqlite+aiosqlite:///./foodflow.db
    path_part = settings.DATABASE_URL.split("///")[-1]
    return Path(path_part).resolve()


def _column_exists(cursor: sqlite3.Cursor, table: str, column: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def _table_exists(cursor: sqlite3.Cursor, table: str) -> bool:
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,)
    )
    return cursor.fetchone() is not None


def _ensure_columns(cursor: sqlite3.Cursor, table: str, columns: Iterable[tuple[str, str]]):
    for name, ddl in columns:
        if _column_exists(cursor, table, name):
            continue
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def _create_shopping_tables(cursor: sqlite3.Cursor):
    if not _table_exists(cursor, "shopping_sessions"):
        cursor.execute(
            """
            CREATE TABLE shopping_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id BIGINT NOT NULL,
                started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                finished_at DATETIME,
                is_active BOOLEAN DEFAULT 1
            )
            """
        )

    if not _table_exists(cursor, "label_scans"):
        cursor.execute(
            """
            CREATE TABLE label_scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                brand TEXT,
                weight TEXT,
                calories INTEGER,
                protein REAL,
                fat REAL,
                carbs REAL,
                matched_product_id INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(session_id) REFERENCES shopping_sessions(id),
                FOREIGN KEY(matched_product_id) REFERENCES products(id)
            )
            """
        )


def _run_sqlite_migrations():
    db_path = _get_sqlite_path()
    if not db_path:
        return

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()

        if _table_exists(cursor, "products"):
            _ensure_columns(
                cursor,
                "products",
                [
                    ("calories", "FLOAT DEFAULT 0.0"),
                    ("protein", "FLOAT DEFAULT 0.0"),
                    ("fat", "FLOAT DEFAULT 0.0"),
                    ("carbs", "FLOAT DEFAULT 0.0"),
                ]
            )

        _create_shopping_tables(cursor)

        # Add onboarding fields to user_settings
        if _table_exists(cursor, "user_settings"):
            _ensure_columns(
                cursor,
                "user_settings",
                [
                    ("gender", "TEXT"),
                    ("height", "INTEGER"),
                    ("weight", "REAL"),
                    ("goal", "TEXT"),
                    ("is_initialized", "BOOLEAN DEFAULT 0"),
                ]
            )

        conn.commit()
    finally:
        conn.close()


async def run_migrations():
    # Only sqlite needs manual migrations for now
    if not settings.DATABASE_URL.startswith("sqlite"):
        return
    await asyncio.to_thread(_run_sqlite_migrations)

