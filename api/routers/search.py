"""Smart Search Router — Fridge Search and AI Summary."""
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, or_
from api.auth import CurrentUser, DBSession
from database.models import Product, Receipt
from services.ai_brain import AIBrainService
import logging

router = APIRouter()
logger = logging.getLogger("api.search")

@router.get("/fridge")
async def search_fridge(
    user: CurrentUser,
    session: DBSession,
    q: str = Query(None),
    with_summary: bool = Query(False)
):
    """Search products with optional AI summary and tags."""
    try:
        # 1. Fetch all products (Fridge is usually small)
        stmt = select(Product).outerjoin(Receipt).where(
            or_(Receipt.user_id == user.id, Product.user_id == user.id)
        ).order_by(Product.id.desc())
        
        all_products = (await session.execute(stmt)).scalars().all()
        
        # 2. Fuzzy Python Search
        filtered = []
        if not q:
            filtered = all_products
        else:
            keywords = q.lower().split()
            for p in all_products:
                name_norm = p.name.lower()
                if all(kw in name_norm for kw in keywords):
                    filtered.append(p)
        
        # 3. Optional AI Summary with Caching
        summary_data = None
        if with_summary and not q: # Only summarize full fridge
            from database.models import UserSettings
            from datetime import datetime, timedelta
            import json
            
            # Fetch User Settings
            settings_stmt = select(UserSettings).where(UserSettings.user_id == user.id)
            user_settings = (await session.execute(settings_stmt)).scalar_one_or_none()
            
            # Check Cache
            cached_data = None
            if user_settings and user_settings.fridge_summary_cache and user_settings.fridge_summary_date:
                if datetime.utcnow() - user_settings.fridge_summary_date < timedelta(hours=24):
                    try:
                        cached_data = json.loads(user_settings.fridge_summary_cache)
                        logger.info(f"AI Summary cache HIT for user {user.id}")
                    except: 
                        cached_data = None
            
            if cached_data:
                summary_data = cached_data
            else:
                product_names = [p.name for p in all_products[:40]]
                if product_names:
                    summary_data = await AIBrainService.summarize_fridge(product_names)
                    if summary_data and user_settings:
                        # Update Cache
                        user_settings.fridge_summary_cache = json.dumps(summary_data, ensure_ascii=False)
                        user_settings.fridge_summary_date = datetime.utcnow()
                        session.add(user_settings)
                        await session.commit()
                        logger.info(f"AI Summary cache UPDATED for user {user.id}")
        
        return {
            "results": [
                {
                    "id": p.id,
                    "name": p.name,
                    "calories": p.calories,
                    "weight_g": p.weight_g,
                    "category": p.category
                } for p in filtered
            ],
            "summary": summary_data.get("summary") if isinstance(summary_data, dict) else summary_data,
            "tags": summary_data.get("tags") if isinstance(summary_data, dict) else []
        }
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
