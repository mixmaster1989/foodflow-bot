"""Authentication router for FoodFlow API."""
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from api.auth import create_access_token, get_current_user_required
from api.dependencies import DBSession, CurrentUser
from api.schemas import Token, UserCreate, UserLogin, UserSettingsRead
from database.models import User, UserSettings

router = APIRouter()


@router.post("/register", response_model=Token)
async def register(user_data: UserCreate, session: DBSession):
    """Register a new user or return existing user's token.
    
    For Telegram users, telegram_id is the unique identifier.
    """
    # Check if user exists
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


@router.get("/me", response_model=UserSettingsRead)
async def get_current_user_info(user: CurrentUser, session: DBSession):
    """Get current user profile and settings."""
    stmt = select(UserSettings).where(UserSettings.user_id == user.id)
    settings = (await session.execute(stmt)).scalar_one_or_none()
    
    if not settings:
        # Create default settings if missing
        settings = UserSettings(user_id=user.id)
        session.add(settings)
        await session.commit()
        await session.refresh(settings)
    
    return settings
