from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from api.auth import (
    CurrentUser,
    DBSession,
    create_access_token,
    pwd_context,
)
from api.schemas import SubscriptionRead, Token, UserCreate, UserLogin, UserSettingsRead, UserSettingsUpdate, WebUserRegister, WebUserLogin
from config import settings
from database.models import Subscription, User, UserSettings

router = APIRouter()


@router.post("/register", response_model=Token)
async def register(user_data: UserCreate, session: DBSession):
    """Register a new user or return existing user's token.

    For Telegram users, telegram_id is the unique identifier.
    """
    # Check if user exists
    print(f"🔐 [AUTH] Register/Login request for ID: {user_data.telegram_id} ({user_data.username})")
    existing = await session.get(User, user_data.telegram_id)

    if not existing:
        # Create new user
        user = User(
            id=user_data.telegram_id,
            username=user_data.username,
        )
        session.add(user)

        # Create default settings
        settings = UserSettings(
            user_id=user_data.telegram_id,
            is_initialized=False,
        )
        session.add(settings)
        await session.commit()

    # Generate token
    access_token = create_access_token(data={"sub": user_data.telegram_id})
    return Token(access_token=access_token)


@router.post("/login", response_model=Token)
async def login(user_data: UserLogin, session: DBSession):
    """Login and get access token.

    For Telegram Web App, validate init_data here (simplified for now).
    """
    user = await session.get(User, user_data.telegram_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found. Please register first.",
        )

    access_token = create_access_token(data={"sub": user_data.telegram_id})
    return Token(access_token=access_token)


class UserMeRead(BaseModel):
    id: int
    first_name: str | None = None
    role: str = "user"
    tier: str = "free"
    is_founding_member: bool = False
    settings: UserSettingsRead
    subscription: SubscriptionRead | None = None


@router.get("/me", response_model=UserMeRead)
async def get_current_user_info(user: CurrentUser, session: DBSession):
    """Get current user profile and settings."""
    stmt = select(UserSettings).where(UserSettings.user_id == user.id)
    user_settings = (await session.execute(stmt)).scalar_one_or_none()

    if not user_settings:
        # Create default settings if missing
        user_settings = UserSettings(user_id=user.id)
        session.add(user_settings)
        await session.commit()
        await session.refresh(user_settings)

    # Fetch subscription
    sub_stmt = select(Subscription).where(Subscription.user_id == user.id)
    subscription = (await session.execute(sub_stmt)).scalar_one_or_none()

    # Sync admin role from config
    # Use explicit integer comparison to avoid any SQLAlchemy/type weirdness
    admin_ids = [int(aid) for aid in settings.ADMIN_IDS]
    if int(user.id) in admin_ids and user.role != "admin":
        user.role = "admin"
        session.add(user)
        await session.commit()
        await session.refresh(user)

    sub_data = None
    tier = "free"
    if subscription:
        # Check if active based on dates and flag
        from datetime import datetime
        import pytz
        msk_tz = pytz.timezone("Europe/Moscow")
        now = datetime.now(msk_tz).replace(tzinfo=None)

        is_active = subscription.is_active and (
            subscription.expires_at is None or subscription.expires_at > now
        )
        
        if is_active:
            tier = subscription.tier

        sub_data = SubscriptionRead(
            tier=subscription.tier,
            starts_at=subscription.starts_at,
            expires_at=subscription.expires_at,
            is_active=is_active,
            auto_renew=subscription.auto_renew
        )

    effective_tier = tier
    if settings.IS_BETA_TESTING:
        effective_tier = "pro"

    return UserMeRead(
        id=user.id,
        first_name=user.username,
        role=user.role,
        tier=effective_tier,
        is_founding_member=getattr(user, "is_founding_member", False),
        settings=user_settings,
        subscription=sub_data
    )

class PasswordLogin(BaseModel):
    telegram_id: int
    password: str


@router.post("/login-password", response_model=Token)
async def login_with_password(data: PasswordLogin, session: DBSession):
    """Login with Telegram ID + password (global or individual)."""
    from utils.auth_utils import generate_user_password

    # 1. Check if user exists first to get their individual password
    user = await session.get(User, data.telegram_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден. Сначала запустите бота в Telegram.",
        )

    # 2. Verify password (Global OR Individual)
    individual_password = generate_user_password(data.telegram_id)
    
    is_global = data.password == settings.GLOBAL_PASSWORD
    is_individual = data.password == individual_password

    if not (is_global or is_individual):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный пароль",
        )

    access_token = create_access_token(data={"sub": data.telegram_id})
    return Token(access_token=access_token)


@router.patch("/settings", response_model=UserSettingsRead)
async def update_settings(
    update_data: UserSettingsUpdate,
    user: CurrentUser,
    session: DBSession
):
    """Update current user settings."""
    stmt = select(UserSettings).where(UserSettings.user_id == user.id)
    settings = (await session.execute(stmt)).scalar_one_or_none()

    if not settings:
        settings = UserSettings(user_id=user.id)
        session.add(settings)

    update_dict = update_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(settings, key, value)

    await session.commit()
    await session.refresh(settings)

    return settings


@router.post("/web-register", response_model=Token)
async def web_register(data: WebUserRegister, session: DBSession):
    """Register a new user via email/password (no Telegram required).
    Issues 3 days of PRO subscription as a welcome gift.
    """
    import random
    from datetime import datetime, timedelta

    # Check email uniqueness
    stmt = select(User).where(User.email == data.email.lower())
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Пользователь с таким email уже зарегистрирован.",
        )

    # Generate unique 15-digit ID (doesn't overlap real Telegram IDs which are ~10 digits)
    while True:
        new_id = random.randint(100_000_000_000_000, 999_999_999_999_999)
        existing_id = await session.get(User, new_id)
        if not existing_id:
            break

    # Hash password
    hashed = pwd_context.hash(data.password)

    # Create user
    user = User(
        id=new_id,
        first_name=data.name,
        email=data.email.lower(),
        password_hash=hashed,
        is_web_only=True,
    )
    session.add(user)

    # Default settings (not yet initialized → triggers onboarding on frontend)
    user_settings = UserSettings(user_id=new_id, is_initialized=False)
    session.add(user_settings)

    # Gift: 3 days PRO subscription
    pro_expires = datetime.now() + timedelta(days=3)
    subscription = Subscription(
        user_id=new_id,
        tier="pro",
        is_active=True,
        expires_at=pro_expires,
    )
    session.add(subscription)

    await session.commit()

    access_token = create_access_token(data={"sub": new_id})
    print(f"🌐 [WEB-REG] New web user registered: {data.email} (ID: {new_id})")
    return Token(access_token=access_token)


@router.post("/web-login", response_model=Token)
async def web_login(data: WebUserLogin, session: DBSession):
    """Login via email + password for web-only users."""
    stmt = select(User).where(User.email == data.email.lower())
    user = (await session.execute(stmt)).scalar_one_or_none()

    if not user or not user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь не найден или вход через email не настроен.",
        )

    if not pwd_context.verify(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный пароль.",
        )

    access_token = create_access_token(data={"sub": user.id})
    return Token(access_token=access_token)
