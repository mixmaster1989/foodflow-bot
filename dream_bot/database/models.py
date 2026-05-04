from datetime import datetime
from sqlalchemy import BigInteger, Column, DateTime, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from .base import Base

class User(Base):
    __tablename__ = "users"
    id = Column(BigInteger, primary_key=True)
    username = Column(String, nullable=True)
    dreams_balance = Column(Integer, default=1) # 1 бесплатный сон
    invited_by = Column(BigInteger, nullable=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)

class DreamLog(Base):
    __tablename__ = "dream_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"))
    dream_text = Column(String)
    interpretation = Column(String)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    cost_usd = Column(Integer, default=0) # Будем хранить в "миллионных долях цента" или просто Float
    created_at = Column(DateTime, default=datetime.now)
