from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import event

from config import settings

# Phase 1: Disable echo for production, enable WAL mode for better concurrency
engine = create_async_engine(settings.DATABASE_URL, echo=False)

# Enable WAL mode for SQLite (better concurrent read/write)
@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")  # Faster, still safe
    cursor.execute("PRAGMA busy_timeout=5000")   # Wait 5s for locks
    cursor.close()

async_session = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with async_session() as session:
        yield session

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

