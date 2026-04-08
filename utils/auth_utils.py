import hashlib
import hmac
from config import settings

def generate_user_password(user_id: int) -> str:
    """
    Generate a deterministic but unique password for a user based on their Telegram ID.
    Uses JWT_SECRET_KEY as a salt.
    """
    secret = settings.JWT_SECRET_KEY.encode()
    message = str(user_id).encode()
    
    # Generate HMAC-SHA256 hash
    h = hmac.new(secret, message, hashlib.sha256).hexdigest()
    
    # Take first 8 characters and make them uppercase/readable
    # We could also use a custom alphabet if we wanted even better readability (no 0/O etc)
    # but hex is 0-9 and a-f so it's quite simple.
    return h[:8].upper()
