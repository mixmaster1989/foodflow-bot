"""FoodFlow API — FastAPI Application."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
import logging
from fastapi.middleware.cors import CORSMiddleware

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api.main")

from api.routers import auth, products, consumption, recipes, weight, shopping_list, reports, receipts, recognize, smart, search, herbalife, universal, assets


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

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
