"""FoodFlow API — FastAPI Application."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api.main")

# Rate limiter (in-memory, per IP)
limiter = Limiter(key_func=get_remote_address)

from api.routers import (
    assets,
    auth,
    consumption,
    herbalife,
    products,
    receipts,
    recipes,
    recognize,
    reports,
    search,
    shopping_list,
    smart,
    universal,
    saved_dishes,
    water,
    weight,
    ai_insight,
    referrals,
    debug,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    print("🚀 FoodFlow API starting...")
    yield
    # Shutdown
    print("👋 FoodFlow API shutting down...")


app = FastAPI(
    title="FoodFlow API",
    description="API for nutrition tracking, receipt OCR, and recipe generation",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Attach rate limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://web.telegram.org",
        "https://vk.com",
        "https://xn--d1aojrdbc.xn--p1ai",
        "https://www.xn--d1aojrdbc.xn--p1ai",
        "https://фудфлоу.рф",
        "https://www.фудфлоу.рф",
        "https://tretyakov-igor.tech",
        "https://www.tretyakov-igor.tech",
        "null",  # Telegram Mini App WebView sends null Origin
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(products.router, prefix="/api/products", tags=["Products"])
app.include_router(consumption.router, prefix="/api/consumption", tags=["Consumption"])
app.include_router(recipes.router, prefix="/api/recipes", tags=["Recipes"])
app.include_router(weight.router, prefix="/api/weight", tags=["Weight"])
app.include_router(shopping_list.router, prefix="/api/shopping-list", tags=["Shopping List"])
app.include_router(reports.router, prefix="/api/reports", tags=["Reports"])
app.include_router(receipts.router, prefix="/api/receipts", tags=["Receipts (OCR)"])
app.include_router(recognize.router, prefix="/api/recognize", tags=["Food Recognition"])
app.include_router(smart.router, prefix="/api/smart", tags=["Smart Features"])
app.include_router(search.router, prefix="/api/search", tags=["Search"])
app.include_router(herbalife.router, prefix="/api/herbalife", tags=["Herbalife Expert"])
app.include_router(universal.router, prefix="/api/universal", tags=["Universal Input"])
app.include_router(assets.router, prefix="/api/assets", tags=["Assets (Flux)"])
app.include_router(saved_dishes.router, prefix="/api/saved-dishes", tags=["Saved Dishes"])
app.include_router(water.router, prefix="/api/water", tags=["Water Tracking"])
app.include_router(ai_insight.router, prefix="/api/ai", tags=["AI Insight"])
app.include_router(referrals.router, prefix="/api/referrals", tags=["Referrals"])
app.include_router(debug.router, prefix="/api/debug", tags=["Debug"])



@app.get("/api/", tags=["Root"])
async def root():
    """Root endpoint — API health check."""
    return {
        "status": "ok",
        "service": "FoodFlow API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/api/health", tags=["Root"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
