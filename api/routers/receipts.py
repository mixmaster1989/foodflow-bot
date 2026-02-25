"""Receipts router for FoodFlow API — OCR and normalization."""
import io
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile
from sqlalchemy import select

from api.auth import DBSession, CurrentUser
from api.schemas import ReceiptParseResult
from database.models import Product, Receipt
from services.normalization import NormalizationService
from services.ocr import OCRService

router = APIRouter()


@router.post("/upload", response_model=ReceiptParseResult)
async def upload_receipt(
    user: CurrentUser,
    session: DBSession,
    file: Annotated[UploadFile, File(description="Receipt image (JPEG/PNG)")],
):
    """Upload receipt image, run OCR, normalize products with КБЖУ.
    
    Returns parsed items with nutritional data. Items are NOT automatically
    added to fridge — frontend should call `/api/products` to add selected items.
    """
    # Validate file type
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image (JPEG/PNG)")
    
    # Read image bytes
    image_bytes = await file.read()
    if len(image_bytes) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=400, detail="Image too large (max 10MB)")
    
    try:
        # Step 1: OCR
        ocr_result = await OCRService.parse_receipt(image_bytes)
        raw_items = ocr_result.get("items", [])
        total = ocr_result.get("total", 0.0)
        
        if not raw_items:
            raise HTTPException(status_code=422, detail="No items found on receipt")
        
        # Step 2: Normalize (add КБЖУ)
        normalized_items = await NormalizationService.normalize_products(raw_items)
        
        # Step 3: Save receipt header
        receipt = Receipt(
            user_id=user.id,
            raw_text=str(ocr_result),
            total_amount=total,
        )
        session.add(receipt)
        await session.commit()
        await session.refresh(receipt)
        
        return ReceiptParseResult(
            receipt_id=receipt.id,
            items=normalized_items,
            total=total,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR processing error: {str(e)}")


@router.post("/{receipt_id}/items/add")
async def add_receipt_item(
    receipt_id: int,
    item_data: dict,
    user: CurrentUser,
    session: DBSession,
):
    """Add a single item from receipt to fridge.
    
    Frontend should call this for each item user wants to add.
    """
    # Verify receipt ownership
    receipt = await session.get(Receipt, receipt_id)
    if not receipt or receipt.user_id != user.id:
        raise HTTPException(status_code=404, detail="Receipt not found")
    
    product = Product(
        receipt_id=receipt_id,
        user_id=user.id,
        name=item_data.get("name", "Unknown"),
        price=float(item_data.get("price", 0)),
        quantity=float(item_data.get("quantity", 1)),
        category=item_data.get("category"),
        calories=float(item_data.get("calories", 0)),
        protein=float(item_data.get("protein", 0)),
        fat=float(item_data.get("fat", 0)),
        carbs=float(item_data.get("carbs", 0)),
        fiber=float(item_data.get("fiber", 0)),
        source="api_receipt",
    )
    session.add(product)
    await session.commit()
    await session.refresh(product)
    
    return {"message": "Item added", "product_id": product.id}
