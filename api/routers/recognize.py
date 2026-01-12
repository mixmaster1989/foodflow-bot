"""Food recognition router for FoodFlow API — AI-powered food analysis."""
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile

from api.dependencies import CurrentUser
from api.schemas import FoodRecognitionResult
from services.ai import AIService

router = APIRouter()


@router.post("/food", response_model=FoodRecognitionResult)
async def recognize_food(
    user: CurrentUser,
    file: Annotated[UploadFile, File(description="Food photo (JPEG/PNG)")],
):
    """Recognize food from photo and get nutritional data (КБЖУ + fiber).
    
    Uses AI vision model to identify the dish and estimate nutritional values.
    Returns data per 100g.
    """
    # Validate file type
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image (JPEG/PNG)")
    
    # Read image bytes
    image_bytes = await file.read()
    if len(image_bytes) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=400, detail="Image too large (max 10MB)")
    
    try:
        result = await AIService.recognize_product_from_image(image_bytes)
        
        if not result or not result.get("name"):
            raise HTTPException(
                status_code=422, 
                detail="Could not recognize food in image. Try a clearer photo."
            )
        
        return FoodRecognitionResult(
            name=result.get("name", "Unknown"),
            calories=float(result.get("calories", 0)),
            protein=float(result.get("protein", 0)),
            fat=float(result.get("fat", 0)),
            carbs=float(result.get("carbs", 0)),
            fiber=float(result.get("fiber", 0)),
            weight_g=float(result.get("weight_g")) if result.get("weight_g") else None,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recognition error: {str(e)}")


@router.post("/label", response_model=FoodRecognitionResult)
async def parse_nutrition_label(
    user: CurrentUser,
    file: Annotated[UploadFile, File(description="Nutrition label photo")],
):
    """Parse nutrition label from photo.
    
    Extracts exact КБЖУ values from product label image.
    """
    from services.label_ocr import LabelOCRService
    
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    image_bytes = await file.read()
    
    try:
        result = await LabelOCRService.parse_label(image_bytes)
        
        if not result:
            raise HTTPException(status_code=422, detail="Could not parse label")
        
        return FoodRecognitionResult(
            name=result.get("name", "Unknown Product"),
            calories=float(result.get("calories", 0) or 0),
            protein=float(result.get("protein", 0) or 0),
            fat=float(result.get("fat", 0) or 0),
            carbs=float(result.get("carbs", 0) or 0),
            fiber=float(result.get("fiber", 0) or 0),
            weight_g=float(result.get("weight")) if result.get("weight") else None,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Label parsing error: {str(e)}")
