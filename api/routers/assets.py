from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from services.flux_service import flux_service
from api.auth import CurrentUser, DBSession
import os
import logging
import asyncio

router = APIRouter()
logger = logging.getLogger("api.assets")

@router.get("/icon/{name}")
async def get_product_icon(name: str):
    """Returns a generated icon for the product name."""
    try:
        path = await flux_service.generate_product_icon(name)
        if not path or not os.path.exists(path):
            raise HTTPException(status_code=500, detail="Generation failed")
        return FileResponse(path)
    except Exception as e:
        logger.error(f"Icon generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/daily-bg")
async def get_daily_background(user: CurrentUser, db: DBSession):
    """Returns a generated daily background based on fridge contents."""
    try:
        # 1. Fetch current fridge product names
        from database.models import Product
        from sqlalchemy import select
        
        stmt = select(Product).where(Product.user_id == user.id)
        result = await db.execute(stmt)
        products = [p.name for p in result.scalars().all()]
        
        if not products:
            products = ["Fresh vegetables", "Fruit basket", "Healthy kitchen"]
            
        # 2. Generate/Get cached collage
        path = await flux_service.generate_daily_collage(products)
        if not path or not os.path.exists(path):
            raise HTTPException(status_code=500, detail="Background generation failed")
            
        return FileResponse(path)
    except Exception as e:
        logger.error(f"Daily background failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
