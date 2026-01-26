"""Herbalife Expert Router."""
from fastapi import APIRouter, HTTPException, Query
from services.herbalife_expert import herbalife_expert
from api.auth import CurrentUser

router = APIRouter()

@router.get("/search")
async def search_herbalife(q: str, user: CurrentUser):
    """Resolve Herbalife product by alias/name."""
    try:
        product = await herbalife_expert.find_product_by_alias(q)
        if not product:
            return {"found": False, "message": "Продукт не найден в базе Herbalife"}
        
        return {
            "found": True,
            "product": product
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/products")
async def list_herbalife_products(user: CurrentUser):
    """List all available Herbalife products."""
    return {"products": herbalife_expert._db.get("products", [])}

@router.post("/calculate")
async def calculate_herbalife_nutrition(product_id: str, amount: float, unit: str, user: CurrentUser):
    """Calculate exact nutrition for a specific amount/unit."""
    product = herbalife_expert.get_product_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    result = herbalife_expert.calculate_nutrition(product, amount, unit)
    return result
