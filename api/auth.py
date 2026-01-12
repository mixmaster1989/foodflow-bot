"""JWT Authentication for FoodFlow API."""
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas import TokenData
from config import settings
from database.base import get_db
from database.models import User

# JWT Configuration
SECRET_KEY = getattr(settings, 'JWT_SECRET_KEY', 'foodflow-super-secret-key-change-in-production')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30

# Password hashing (for future use)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create JWT access token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> TokenData | None:
    """Verify JWT token and extract data."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("sub")
        if user_id is None:
            return None
        return TokenData(user_id=user_id)
    except JWTError:
        return None


async def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)]
) -> User | None:
    """Get current user from JWT token.
    
    Returns None if no token or invalid token (for optional auth).
    Raises 401 if token is present but invalid.
    """
    if not token:
        return None
    
    token_data = verify_token(token)
    if not token_data or not token_data.user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    async for session in get_db():
        user = await session.get(User, token_data.user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )
        return user
    return None


async def get_current_user_required(
    user: Annotated[User | None, Depends(get_current_user)]
) -> User:
    """Require authenticated user (raises 401 if not authenticated)."""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
