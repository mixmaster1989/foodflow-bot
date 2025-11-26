from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    BOT_TOKEN: str
    OPENROUTER_API_KEY: str
    DATABASE_URL: str = "sqlite+aiosqlite:///./foodflow.db" # Default to SQLite for easy local dev on Windows

    # Paths
    BASE_DIR: Path = Path(__file__).resolve().parent

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# Force loading .env from the same directory as config.py
settings = Settings(_env_file=Path(__file__).resolve().parent / ".env")
