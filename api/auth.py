"""JWT Authentication for FoodFlow API."""
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import Depends, HTTPException, status, Query
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas import TokenData
import logging
from config import settings
from database.base import get_db
from database.models import User

logger = logging.getLogger("api.auth")

# JWT Configuration
SECRET_KEY = settings.JWT_SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30

# Password hashing (for future use)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create JWT access token with stringified sub."""
    to_encode = data.copy()
    
    # CRITICAL: Subject MUST be a string for many JWT libraries
    if "sub" in to_encode:
        to_encode["sub"] = str(to_encode["sub"])
        
    expire = datetime.utcnow() + (expires_delta or timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> TokenData | None:
    """Verify JWT token and extract data."""
    try:
        # Standard decode
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            logger.warning("[Auth] Token missing 'sub' claim")
            return None
        return TokenData(user_id=int(user_id))
    except JWTError as e:
        logger.error(f"[Auth] JWT Decode Error: {e}")
        return None
    except (ValueError, TypeError) as e:
        logger.error(f"[Auth] Token Data Error: {e}")
        return None


async def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)] = None,
    token_query: Annotated[str | None, Query(alias="token")] = None,
    # Need to avoid circular import by using dynamic import or manual session
    session: Annotated[AsyncSession, Depends(get_db)] = None 
) -> User | None:
    """Get current user from JWT token (header or query param)."""
    final_token = token or token_query
    if not final_token:
        return None
    
    token_data = verify_token(final_token)
    if not token_data or not token_data.user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get user directly from session
    # We use __import__ trick if dependencies are nested, but get_db is usually safe
    user = await session.get(User, token_data.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


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


# Shortcut for cleaner dependency injection in routers
CurrentUser = Annotated[User, Depends(get_current_user_required)]
DBSession = Annotated[AsyncSession, Depends(get_db)]
