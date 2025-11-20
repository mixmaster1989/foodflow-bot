from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, BigInteger
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
    
    receipt = relationship("Receipt", back_populates="products")

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
