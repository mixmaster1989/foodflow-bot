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

from database.base import Base


class User(Base):
    __tablename__ = "users"
    id = Column(BigInteger, primary_key=True)  # Telegram ID
    username = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    receipts = relationship("Receipt", back_populates="user")
    consumption_logs = relationship("ConsumptionLog", back_populates="user")
    shopping_sessions = relationship("ShoppingSession", back_populates="user")

class Receipt(Base):
    __tablename__ = "receipts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"))
    raw_text = Column(String, nullable=True)
    total_amount = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="receipts")
    products = relationship("Product", back_populates="receipt")

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, autoincrement=True)
    receipt_id = Column(Integer, ForeignKey("receipts.id"))
    name = Column(String, nullable=False)
    quantity = Column(Float, default=1.0)
    price = Column(Float, nullable=False)
    category = Column(String, nullable=True)
    calories = Column(Float, default=0.0)
    protein = Column(Float, default=0.0)
    fat = Column(Float, default=0.0)
    carbs = Column(Float, default=0.0)
    receipt = relationship("Receipt", back_populates="products")
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
    date = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="consumption_logs")

class ShoppingSession(Base):
    __tablename__ = "shopping_sessions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
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
    matched_product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
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
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", backref="price_tags")

class UserSettings(Base):
    __tablename__ = "user_settings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), unique=True, nullable=False)
    calorie_goal = Column(Integer, default=2000)
    protein_goal = Column(Integer, default=150)
    fat_goal = Column(Integer, default=70)
    carb_goal = Column(Integer, default=250)
    allergies = Column(String, nullable=True)  # Comma-separated list
    user = relationship("User", backref="settings")

class ShoppingListItem(Base):
    __tablename__ = "shopping_list_items"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    product_name = Column(String, nullable=False)
    is_bought = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
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
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        # Ensure uniqueness per user+hash+title to avoid duplicate entries
        # (SQLAlchemy syntax for composite unique constraint)
        # Note: SQLite supports this.
        # Unique constraint is optional but helpful.
        # If you need it, uncomment the line below.
        # UniqueConstraint('user_id', 'ingredients_hash', 'title', name='uq_cached_recipe'),
    )
