from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship

PAYMENT_SOURCE_STARS = "stars"
PAYMENT_SOURCE_YOOKASSA = "yookassa"
PAYMENT_SOURCE_TRIAL = "trial"
PAYMENT_SOURCE_REFERRAL = "referral"
PAYMENT_SOURCE_FEEDBACK = "feedback_bonus"
PAYMENT_SOURCE_ADMIN = "admin_grant"
PAID_SOURCES = (PAYMENT_SOURCE_STARS, PAYMENT_SOURCE_YOOKASSA)

from database.base import Base


class User(Base):
    __tablename__ = "users"
    id = Column(BigInteger, primary_key=True)  # Telegram ID
    username = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    is_verified = Column(Boolean, default=False)
    role = Column(String, default="user")
    curator_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    referral_token = Column(String, unique=True, nullable=True)
    invited_by_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    ref_paid_count = Column(Integer, default=0)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    language_code = Column(String, nullable=True)
    is_premium = Column(Boolean, default=False)
    is_founding_member = Column(Boolean, default=False)
    last_activity = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    referral_token_expires_at = Column(DateTime, nullable=True)
    onboarding_reminded = Column(Boolean, default=False)
    # Web-only registration fields
    email = Column(String, unique=True, nullable=True)
    password_hash = Column(String, nullable=True)
    is_web_only = Column(Boolean, default=False)
    is_blocked = Column(Boolean, default=False)
    
    # VK Integration
    vk_id = Column(BigInteger, unique=True, nullable=True, index=True)

    # Relationships
    receipts = relationship("Receipt", back_populates="user")
    consumption_logs = relationship("ConsumptionLog", back_populates="user")
    shopping_sessions = relationship("ShoppingSession", back_populates="user")
    wards = relationship("User", backref="curator", remote_side=[id], foreign_keys=[curator_id])
    invited_users = relationship("User", backref="inviter", remote_side=[id], foreign_keys=[invited_by_id])
    water_logs = relationship("WaterLog", back_populates="user")
    subscription = relationship("Subscription", back_populates="user", uselist=False)

class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, unique=True) # 1 to 1
    tier = Column(String, default="free") # "free", "basic", "pro"
    starts_at = Column(DateTime, default=datetime.now)
    expires_at = Column(DateTime, nullable=True) # Если None - бесконечно
    is_active = Column(Boolean, default=True)
    telegram_payment_charge_id = Column(String, nullable=True)  # For refunds & subscription management
    auto_renew = Column(Boolean, default=True)  # Auto-renewal status
    payment_source = Column(String, nullable=True)  # stars|yookassa|trial|referral|feedback_bonus|admin_grant
    yookassa_payment_id = Column(String, nullable=True)  # YooKassa payment.id for webhook reconciliation

    user = relationship("User", back_populates="subscription")

class Receipt(Base):
    __tablename__ = "receipts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"))
    raw_text = Column(String, nullable=True)
    total_amount = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    user = relationship("User", back_populates="receipts")
    products = relationship("Product", back_populates="receipt")

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, autoincrement=True)
    receipt_id = Column(Integer, ForeignKey("receipts.id"), nullable=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=True, index=True)  # INDEX for fridge queries
    name = Column(String, nullable=False)
    quantity = Column(Float, default=1.0)
    price = Column(Float, nullable=False)
    weight_g = Column(Float, nullable=True)  # Total weight in grams (if applicable)
    category = Column(String, nullable=True)
    calories = Column(Float, default=0.0)
    protein = Column(Float, default=0.0)
    fat = Column(Float, default=0.0)
    carbs = Column(Float, default=0.0)
    fiber = Column(Float, default=0.0) # NEW: Fiber tracking
    base_name = Column(String, nullable=True) # NEW: Product essence for KBJU matching
    source = Column(String, default="receipt")  # receipt | fridge_init | manual | other
    receipt = relationship("Receipt", back_populates="products")
    user = relationship("User", backref="products")
    label_scans = relationship("LabelScan", back_populates="matched_product")

class ConsumptionLog(Base):
    __tablename__ = "consumption_logs"
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.id"))
    product_name = Column(String, nullable=False)
    calories = Column(Float, default=0.0)
    protein = Column(Float, default=0.0)
    fat = Column(Float, default=0.0)
    carbs = Column(Float, default=0.0)
    date = Column(DateTime, default=datetime.now)
    fiber = Column(Float, default=0.0)
    base_name = Column(String, nullable=True)
    user = relationship("User", back_populates="consumption_logs")

class SavedDish(Base):
    __tablename__ = "saved_dishes"
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    dish_type = Column(String, default="dish")  # "dish" or "meal"
    components = Column(JSON, nullable=False) # List of dicts: [{name, weight, calories...}]

    # Pre-calculated totals for quick logging
    total_calories = Column(Float, default=0.0)
    total_protein = Column(Float, default=0.0)
    total_fat = Column(Float, default=0.0)
    total_carbs = Column(Float, default=0.0)
    total_fiber = Column(Float, default=0.0)

    created_at = Column(DateTime, default=datetime.now)
    user = relationship("User", backref="saved_dishes")

class ShoppingSession(Base):
    __tablename__ = "shopping_sessions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    started_at = Column(DateTime, default=datetime.now)
    finished_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    user = relationship("User", back_populates="shopping_sessions")
    label_scans = relationship("LabelScan", back_populates="session")

class LabelScan(Base):
    __tablename__ = "label_scans"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("shopping_sessions.id"), nullable=False)
    name = Column(String, nullable=False)
    brand = Column(String, nullable=True)
    weight = Column(String, nullable=True)
    calories = Column(Integer, nullable=True)
    protein = Column(Float, nullable=True)
    fat = Column(Float, nullable=True)
    carbs = Column(Float, nullable=True)
    fiber = Column(Float, default=0.0) # NEW: Fiber tracking
    matched_product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    session = relationship("ShoppingSession", back_populates="label_scans")
    matched_product = relationship("Product", back_populates="label_scans")

class PriceTag(Base):
    __tablename__ = "price_tags"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    product_name = Column(String, nullable=False)
    volume = Column(String, nullable=True)  # e.g., "500 мл", "1 кг", "300 г"
    price = Column(Float, nullable=False)
    store_name = Column(String, nullable=True)
    location = Column(String, nullable=True)  # для будущей геолокации
    photo_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    user = relationship("User", backref="price_tags")

class UserSettings(Base):
    __tablename__ = "user_settings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), unique=True, nullable=False)
    calorie_goal = Column(Integer, default=2000)
    protein_goal = Column(Integer, default=150)
    fat_goal = Column(Integer, default=70)
    carb_goal = Column(Integer, default=250)
    allergies = Column(String, nullable=True)
    gender = Column(String, nullable=True)
    height = Column(Integer, nullable=True)
    weight = Column(Float, nullable=True)
    goal = Column(String, nullable=True)
    is_initialized = Column(Boolean, default=False)
    age = Column(Integer, nullable=True)
    reminder_time = Column(String, default="09:00")
    reminders_enabled = Column(Boolean, default=True)
    fiber_goal = Column(Integer, default=30)
    summary_time = Column(String, default="21:00")
    fridge_summary_cache = Column(String, nullable=True)
    fridge_summary_date = Column(DateTime, nullable=True)
    water_goal = Column(Integer, default=2000)
    curator_summary_time = Column(String, default="08:00")  # Время утренней сводки для кураторов
    # Recipe limits
    recipe_refresh_count = Column(Integer, default=0)
    last_recipe_refresh_date = Column(String, nullable=True) # ISO format date
    
    # AI Guide settings
    guide_config = Column(JSON, nullable=True) # Onboarding answers & personality
    guide_active_until = Column(DateTime, nullable=True)
    
    user = relationship("User", backref="settings")

class UserActivity(Base):
    """Tracks feature usage for the AI Guide missions and suggestions."""
    __tablename__ = "user_activity"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    feature_name = Column(String, nullable=False) # e.g., "fridge", "recipes", "weight", "water"
    last_used_at = Column(DateTime, default=datetime.now)
    
    user = relationship("User", backref="activities")

class ShoppingListItem(Base):
    __tablename__ = "shopping_list_items"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    product_name = Column(String, nullable=False)
    is_bought = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    user = relationship("User", backref="shopping_list")

# NEW: Cached recipes for recipe bot
class CachedRecipe(Base):
    __tablename__ = "cached_recipes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    ingredients_hash = Column(String, nullable=False, index=True)  # deterministic hash of sorted ingredient list
    category = Column(String, nullable=False)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    calories = Column(Float, nullable=True)
    ingredients = Column(JSON, nullable=False)  # list of {name, amount}
    steps = Column(JSON, nullable=False)       # list of strings
    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        # Ensure uniqueness per user+hash+title to avoid duplicate entries
        # (SQLAlchemy syntax for composite unique constraint)
        # Note: SQLite supports this.
        # Unique constraint is optional but helpful.
        # If you need it, uncomment the line below.
        # UniqueConstraint('user_id', 'ingredients_hash', 'title', name='uq_cached_recipe'),
    )


class WaterLog(Base):
    __tablename__ = "water_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    amount_ml = Column(Integer, nullable=False)
    date = Column(DateTime, default=datetime.now)

    user = relationship("User", back_populates="water_logs")


class WeightLog(Base):
    """Model for tracking user weight over time."""
    __tablename__ = "weight_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    weight = Column(Float, nullable=False)
    recorded_at = Column(DateTime, default=datetime.now)
    user = relationship("User", backref="weight_logs")


class Marathon(Base):
    """Marathon managed by a curator."""
    __tablename__ = "marathons"
    id = Column(Integer, primary_key=True, autoincrement=True)
    curator_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True)
    is_registration_open = Column(Boolean, default=True) # Can users join via link?
    invite_token = Column(String, unique=True, nullable=True)
    invite_token_expires_at = Column(DateTime, nullable=True)

    # Store wave configuration [start, end, label]
    waves_config = Column(JSON, nullable=True)

    # Points Customization
    points_name = Column(String, default="Снежинки")
    points_emoji = Column(String, default="❄️")

    created_at = Column(DateTime, default=datetime.now)
    curator = relationship("User", backref="marathons", foreign_keys=[curator_id])
    participants = relationship("MarathonParticipant", back_populates="marathon")


class MarathonParticipant(Base):
    """Participant in a specific marathon."""
    __tablename__ = "marathon_participants"
    id = Column(Integer, primary_key=True, autoincrement=True)
    marathon_id = Column(Integer, ForeignKey("marathons.id"), nullable=False)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)

    start_weight = Column(Float, nullable=True) # Weight at entry
    final_weight = Column(Float, nullable=True) # Weight at exit/finish

    # Cached totals for quick leadership board
    total_snowflakes = Column(Integer, default=0)

    is_active = Column(Boolean, default=True) # If kicked -> False
    joined_at = Column(DateTime, default=datetime.now)

    marathon = relationship("Marathon", back_populates="participants")
    user = relationship("User", backref="marathon_participations")
    snowflake_logs = relationship("SnowflakeLog", back_populates="participant")


class SnowflakeLog(Base):
    """Log of activity points (snowflakes) assigned by curator."""
    __tablename__ = "snowflake_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    participant_id = Column(Integer, ForeignKey("marathon_participants.id"), nullable=False)
    curator_id = Column(BigInteger, ForeignKey("users.id"), nullable=False) # Audit who gave points
    amount = Column(Integer, nullable=False) # Can be negative
    reason = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.now)

    participant = relationship("MarathonParticipant", back_populates="snowflake_logs")


class ReferralEvent(Base):
    """Audit log of referral-related events."""
    __tablename__ = "referral_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    referrer_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    invitee_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    event_type = Column(String, nullable=False)  # "signup", "paid", "bonus_activated"
    tier = Column(String, nullable=True)  # basic / pro / curator, if applicable
    created_at = Column(DateTime, default=datetime.now)


class ReferralReward(Base):
    """Pending or activated referral rewards (bonus days of tariffs)."""
    __tablename__ = "referral_rewards"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    reward_type = Column(String, nullable=False)  # "basic_days", "pro_days", "curator_days"
    days = Column(Integer, nullable=False)
    source = Column(String, nullable=False)  # "ref_invite_paid", "ref_10_paid", "ad_campaign", "curator_ref_paid", etc.
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    activated_at = Column(DateTime, nullable=True)

class UserFeedback(Base):
    """Model for saving user answers to polls/surveys."""
    __tablename__ = "user_feedback"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    feedback_type = Column(String, nullable=False) # e.g. "inactive_poll"
    answer = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.now)

    user = relationship("User", backref="feedbacks")

class CanonicalProduct(Base):
    """Cached (canonical) KBJU data for products to avoid redundant AI calls."""
    __tablename__ = "canonical_products"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    base_name = Column(String, unique=True, nullable=False, index=True)
    display_name = Column(String, nullable=True)
    category = Column(String, nullable=True)
    
    calories = Column(Float, default=0.0)
    protein = Column(Float, default=0.0)
    fat = Column(Float, default=0.0)
    carbs = Column(Float, default=0.0)
    fiber = Column(Float, default=0.0)
    
    source = Column(String, default="ai_gemini_2_5")
    per_unit = Column(String, default="per_100g")
    
    version = Column(Integer, default=1)
    is_verified = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
class GuideHistory(Base):
    """Stores conversation history between the user and the AI Guide."""
    __tablename__ = "guide_history"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    role = Column(String, nullable=False) # "user", "assistant", "system", "summary"
    content = Column(String, nullable=False)
    tokens = Column(Integer, default=0) # Estimated tokens
    is_summary = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    
    user = relationship("User", backref="guide_histories")
