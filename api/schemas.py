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


class WebUserRegister(BaseModel):
    email: str
    password: str
    name: str


class WebUserLogin(BaseModel):
    email: str
    password: str


# === User Settings ===
class UserSettingsRead(BaseModel):
    calorie_goal: int = 2000
    protein_goal: int = 150
    fat_goal: int = 70
    carb_goal: int = 250
    fiber_goal: int = 30
    water_goal: int = 2000
    allergies: str | None = None
    gender: str | None = None
    age: int | None = None
    height: int | None = None
    weight: float | None = None
    goal: str | None = None
    is_initialized: bool = False

    class Config:
        from_attributes = True


class UserSettingsUpdate(BaseModel):
    calorie_goal: int | None = None
    protein_goal: int | None = None
    fat_goal: int | None = None
    carb_goal: int | None = None
    fiber_goal: int | None = None
    water_goal: int | None = None
    allergies: str | None = None
    gender: str | None = None
    age: int | None = None
    height: int | None = None
    weight: float | None = None
    goal: str | None = None
    is_initialized: bool | None = None


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
    weight_g: float | None = None
    date: datetime | None = None


class ConsumptionLogUpdate(BaseModel):
    product_name: str | None = None
    calories: float | None = None
    protein: float | None = None
    fat: float | None = None
    carbs: float | None = None
    fiber: float | None = None
    date: datetime | None = None


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


class LabelParseResult(BaseModel):
    name: str | None = None
    brand: str | None = None
    weight: str | None = None
    calories: float = 0.0
    protein: float = 0.0
    fat: float = 0.0
    carbs: float = 0.0
    fiber: float = 0.0


class FridgeSummary(BaseModel):
    total_items: int
    total_calories: float
    recently_added: list[ProductRead]


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


# === Water ===
class WaterLogCreate(BaseModel):
    amount_ml: int = Field(..., gt=0, le=2000)


class WaterLogRead(BaseModel):
    id: int
    amount_ml: int
    date: datetime

    class Config:
        from_attributes = True


# === Subscriptions ===
class SubscriptionRead(BaseModel):
    tier: str
    starts_at: datetime | None = None
    expires_at: datetime | None = None
    is_active: bool = False
    auto_renew: bool = True

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
    protein_goal: float
    fat: float
    fat_goal: float
    carbs: float
    carb_goal: float
    fiber: float
    fiber_goal: float
    meals_count: int

# === Saved Dishes ===
class SavedDishComponent(BaseModel):
    name: str
    calories: float
    protein: float
    fat: float
    carbs: float
    fiber: float
    weight_g: float | None = None

class SavedDishCreate(BaseModel):
    name: str
    dish_type: str = "dish"
    components: list[SavedDishComponent]
    total_calories: float
    total_protein: float
    total_fat: float
    total_carbs: float
    total_fiber: float

class SavedDishRead(BaseModel):
    id: int
    name: str
    dish_type: str
    components: list[SavedDishComponent]
    total_calories: float
    total_protein: float
    total_fat: float
    total_carbs: float
    total_fiber: float

    class Config:
        from_attributes = True

class SavedDishLog(BaseModel):
    date: str | None = None


# === Referrals ===
class ReferralRewardPendingRead(BaseModel):
    id: int
    reward_type: str
    days: int
    source: str


class ReferralMeResponse(BaseModel):
    signup_count: int
    paid_count: int
    ref_paid_count: int
    has_month_pro_bonus: bool
    pending_rewards: list[ReferralRewardPendingRead]
    active_basic_days: int
    active_pro_days: int
    active_curator_days: int
    referral_link: str | None = None
    referral_token_expires_at: datetime | None = None


class ReferralGenerateLinkRequest(BaseModel):
    days: int | None = None


class ReferralGenerateLinkResponse(BaseModel):
    referral_link: str
    referral_token_expires_at: datetime | None = None


class ReferralActivateRequest(BaseModel):
    reward_id: int
