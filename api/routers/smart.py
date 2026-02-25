"""Smart Analysis Router."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from api.auth import CurrentUser, DBSession
from services.normalization import NormalizationService

router = APIRouter()

class AnalyzeRequest(BaseModel):
    text: str

class AnalyzedProduct(BaseModel):
    name: str = "Unknown"
    calories: float = 0
    protein: float = 0
    fat: float = 0
    carbs: float = 0
    weight_g: float | None = None
    fiber: float= 0

@router.post("/analyze", response_model=AnalyzedProduct)
async def analyze_text(request: AnalyzeRequest, user: CurrentUser):
    """Analyze text description of food."""
    try:
        result = await NormalizationService.analyze_food_intake(request.text)
        
        # Safe extraction
        return AnalyzedProduct(
            name=result.get("name", request.text),
            calories=float(result.get("calories", 0)),
            protein=float(result.get("protein", 0)),
            fat=float(result.get("fat", 0)),
            carbs=float(result.get("carbs", 0)),
            fiber=float(result.get("fiber", 0)),
            weight_g=float(result.get("weight_grams")) if result.get("weight_grams") else None
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
