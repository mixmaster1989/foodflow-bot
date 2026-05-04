from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    BOT_TOKEN: str
    RECEPTION_BOT_TOKEN: str | None = None
    OPENROUTER_API_KEY: str
    GROK_PROXY: str | None = None
    DATABASE_URL: str = "sqlite+aiosqlite:////home/user1/foodflow-bot/foodflow.db"
    JWT_SECRET_KEY: str
    GLOBAL_PASSWORD: str
    ADMIN_IDS: list[int] = [432823154]
    PILOT_USER_IDS: list[int] = [33587682, 295543071, 432823154]  # Vasily, Olga, and Admin (User)
    PAYMENT_PROVIDER_TOKEN: str | None = None  # Legacy Telegram payment token
    YOOKASSA_SHOP_ID: str | None = None
    YOOKASSA_SECRET_KEY: str | None = None
    IS_BETA_TESTING: bool = True
    MARKETING_GROUP_ID: int = 0

    # Content Factory publishing (optional)
    CONTENT_FACTORY_TELEGRAM_TOKEN: str | None = None
    CONTENT_FACTORY_TARGET_CHAT_ID: int | None = None
    
    # VK Mini App
    VK_APP_ID: int = 54530169
    VK_APP_SECRET: str = ""  # To be set in .env

    # VK publishing (optional)
    VK_TOKEN: str | None = None
    VK_GROUP_ID: int | None = None
    VK_API_VERSION: str = "5.199"


    # Paths
    BASE_DIR: Path = Path(__file__).resolve().parent

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

# Force loading .env from the same directory as config.py
settings = Settings(_env_file=Path(__file__).resolve().parent / ".env")
