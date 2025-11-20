from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, BigInteger, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from FoodFlow.database.base import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(BigInteger, primary_key=True) # Telegram ID
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
