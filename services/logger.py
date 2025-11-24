import logging
import os

# Ensure logs directory exists
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")
os.makedirs(log_dir, exist_ok=True)

log_file = os.path.join(log_dir, "recipe_bot.log")

logger = logging.getLogger("recipe_bot")
logger.setLevel(logging.INFO)

# File handler with UTF‑8 encoding
file_handler = logging.FileHandler(log_file, encoding="utf-8")
formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Optional console handler for debugging during development
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

def log_request(user_id: int, ingredients: list, category: str, prompt: str):
    logger.info(
        f"User {user_id} | Category: {category} | Ingredients: {ingredients} | Prompt: {prompt}"
    )

def log_response(user_id: int, response_json: dict, from_cache: bool):
    source = "CACHE" if from_cache else "AI"
    logger.info(
        f"User {user_id} | Source: {source} | Response: {response_json}"
    )

def log_error(user_id: int, error: Exception):
    logger.error(f"User {user_id} | Error: {error}")
