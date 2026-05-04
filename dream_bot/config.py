import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN_DREAM") # Будем использовать отдельный токен если есть, или основной
if not TELEGRAM_TOKEN:
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
GROK_PROXY = os.getenv("GROK_PROXY")
DATABASE_URL = "sqlite+aiosqlite:///dream_oracle.db"

# Цены и лимиты
FREE_DREAMS = 1
DREAM_PRICE_STARS = 15 # ~10-15 руб
REFERRAL_BONUS = 1
