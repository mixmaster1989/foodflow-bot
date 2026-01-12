from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    BOT_TOKEN: str
    OPENROUTER_API_KEY: str
    DATABASE_URL: str = "sqlite+aiosqlite:///./foodflow.db" # Default to SQLite for easy local dev on Windows
    GLOBAL_PASSWORD: str = "Welcome2026"  # Password for new users
    ADMIN_IDS: list[int] = [432823154]


    # Paths
    BASE_DIR: Path = Path(__file__).resolve().parent

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

# Force loading .env from the same directory as config.py
settings = Settings(_env_file=Path(__file__).resolve().parent / ".env")
