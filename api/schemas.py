"""Pydantic schemas for FoodFlow API."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# === Auth ===
class UserCreate(BaseModel):
    telegram_id: int
    username: str | None = None


class UserLogin(BaseModel):
    telegram_id: int
    # In production, add password or Telegram Web App init data validation


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: int | None = None


# === User Settings ===
class UserSettingsRead(BaseModel):
    calorie_goal: int = 2000
    protein_goal: int = 150
    fat_goal: int = 70
    carb_goal: int = 250
    fiber_goal: int = 30
    allergies: str | None = None
    gender: str | None = None
    age: int | None = None
    height: int | None = None
    weight: float | None = None
    goal: str | None = None

    class Config:
        from_attributes = True


class UserSettingsUpdate(BaseModel):
    calorie_goal: int | None = None
    protein_goal: int | None = None
    fat_goal: int | None = None
    carb_goal: int | None = None
    fiber_goal: int | None = None
    allergies: str | None = None


# === Products ===
class ProductBase(BaseModel):
    name: str
    price: float = 0.0
    quantity: float = 1.0
    weight_g: float | None = None
    category: str | None = None
    calories: float = 0.0
    protein: float = 0.0
    fat: float = 0.0
    carbs: float = 0.0
    fiber: float = 0.0


class ProductCreate(ProductBase):
    pass


class ProductRead(ProductBase):
    id: int
    receipt_id: int | None = None
    user_id: int | None = None
    source: str = "api"

    class Config:
        from_attributes = True


class ProductList(BaseModel):
    items: list[ProductRead]
    total: int
    page: int
    page_size: int


class ConsumeRequest(BaseModel):
    amount: float = Field(..., gt=0, description="Amount to consume")
    unit: Literal["grams", "qty"] = "grams"


# === Consumption Logs ===
class ConsumptionLogBase(BaseModel):
    product_name: str
    calories: float = 0.0
    protein: float = 0.0
    fat: float = 0.0
    carbs: float = 0.0
    fiber: float = 0.0


class ConsumptionLogCreate(ConsumptionLogBase):
    pass


class ConsumptionLogRead(ConsumptionLogBase):
    id: int
    user_id: int
    date: datetime

    class Config:
        from_attributes = True


# === Food Recognition ===
class FoodRecognitionResult(BaseModel):
    name: str
    calories: float
    protein: float
    fat: float
    carbs: float
    fiber: float
    weight_g: float | None = None


# === Receipts ===
class ReceiptItemRaw(BaseModel):
    name: str
    price: float
    quantity: float = 1.0


class ReceiptParseResult(BaseModel):
    receipt_id: int
    items: list[dict]  # Normalized items with КБЖУ
    total: float


# === Recipes ===
class RecipeRequest(BaseModel):
    category: str
    refresh: bool = False


class RecipeRead(BaseModel):
    title: str
    description: str | None = None
    calories: float | None = None
    ingredients: list[dict]
    steps: list[str]


# === Weight ===
class WeightLogCreate(BaseModel):
    weight: float = Field(..., ge=20, le=300)


class WeightLogRead(BaseModel):
    id: int
    weight: float
    recorded_at: datetime

    class Config:
        from_attributes = True


# === Shopping List ===
class ShoppingListItemCreate(BaseModel):
    product_name: str


class ShoppingListItemRead(BaseModel):
    id: int
    product_name: str
    is_bought: bool
    created_at: datetime

    class Config:
        from_attributes = True


# === Reports ===
class DailyReport(BaseModel):
    date: str
    calories_consumed: float
    calories_goal: float
    protein: float
    fat: float
    carbs: float
    fiber: float
    fiber_goal: float
    meals_count: int
