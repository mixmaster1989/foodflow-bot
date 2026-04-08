from datetime import datetime
from typing import Annotated

import pytz
from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select

from api.auth import CurrentUser, DBSession
from api.schemas import (
    ConsumeRequest,
    FridgeSummary,
    LabelParseResult,
    ProductCreate,
    ProductList,
    ProductRead,
)
from database.models import ConsumptionLog, Product, Receipt
from services.label_ocr import LabelOCRService

router = APIRouter()


@router.get("", response_model=ProductList)
async def list_products(
    user: CurrentUser,
    session: DBSession,
    query: str | None = Query(None, description="Search products by name"),
    page: int = Query(0, ge=0),
    page_size: int = Query(20, ge=1, le=100),
):
    """List all products in user's fridge."""
    # Count total
    count_stmt = (
        select(func.count(Product.id))
        .where(Product.user_id == user.id)
    )
    if query:
        count_stmt = count_stmt.where(Product.name.ilike(f"%{query}%"))

    total = await session.scalar(count_stmt) or 0

    # Fetch page
    stmt = (
        select(Product)
        .where(Product.user_id == user.id)
    )
    if query:
        stmt = stmt.where(Product.name.ilike(f"%{query}%"))

    stmt = stmt.order_by(Product.id.desc()).offset(page * page_size).limit(page_size)
    products = (await session.execute(stmt)).scalars().all()

    return ProductList(
        items=[ProductRead.model_validate(p) for p in products],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/summary", response_model=FridgeSummary)
async def get_fridge_summary(user: CurrentUser, session: DBSession):
    """Get fridge summary (bot parity)."""
    # Total items
    total_items = await session.scalar(
        select(func.count(Product.id)).where(Product.user_id == user.id)
    ) or 0

    # Total calories (sum of calories * quantity)
    total_calories = await session.scalar(
        select(func.sum(Product.calories * Product.quantity)).where(Product.user_id == user.id)
    ) or 0.0

    # Recently added (last 5)
    stmt = (
        select(Product)
        .where(Product.user_id == user.id)
        .order_by(Product.id.desc())
        .limit(5)
    )
    products = (await session.execute(stmt)).scalars().all()

    return FridgeSummary(
        total_items=total_items,
        total_calories=total_calories,
        recently_added=[ProductRead.model_validate(p) for p in products],
    )


@router.post("/scan-label", response_model=LabelParseResult)
async def scan_product_label(
    user: CurrentUser,
    file: Annotated[UploadFile, File(description="Product label image")],
):
    """Scan product label (bot parity)."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    image_bytes = await file.read()
    try:
        result = await LabelOCRService.parse_label(image_bytes)
        if not result:
            raise HTTPException(status_code=422, detail="Failed to parse label")

        return LabelParseResult(**result)
    except Exception as e:
        logger.error(f"Label OCR error: {e}")
        raise HTTPException(status_code=500, detail="OCR processing error")


@router.get("/{product_id}", response_model=ProductRead)
async def get_product(product_id: int, user: CurrentUser, session: DBSession):
    """Get product details by ID."""
    product = await session.get(Product, product_id)

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Check ownership
    owner_id = product.user_id
    if product.receipt_id:
        receipt = await session.get(Receipt, product.receipt_id)
        if receipt:
            owner_id = receipt.user_id

    if owner_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return ProductRead.model_validate(product)


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
async def create_product(product_data: ProductCreate, user: CurrentUser, session: DBSession):
    """Add a new product to fridge."""
    product = Product(
        user_id=user.id,
        source="api",
        name=product_data.name,
        price=product_data.price,
        quantity=product_data.quantity,
        weight_g=product_data.weight_g,
        category=product_data.category,
        calories=product_data.calories,
        protein=product_data.protein,
        fat=product_data.fat,
        carbs=product_data.carbs,
        fiber=product_data.fiber,
    )
    session.add(product)
    await session.commit()
    await session.refresh(product)
    return ProductRead.model_validate(product)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(product_id: int, user: CurrentUser, session: DBSession):
    """Delete a product from fridge."""
    product = await session.get(Product, product_id)

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Check ownership
    owner_id = product.user_id
    if product.receipt_id:
        receipt = await session.get(Receipt, product.receipt_id)
        if receipt:
            owner_id = receipt.user_id

    if owner_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    await session.delete(product)
    await session.commit()


@router.post("/{product_id}/consume")
async def consume_product(
    product_id: int,
    consume_data: ConsumeRequest,
    user: CurrentUser,
    session: DBSession,
):
    """Consume a product (log to consumption and optionally reduce quantity)."""
    product = await session.get(Product, product_id)

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Calculate consumed values
    if consume_data.unit == "grams":
        factor = consume_data.amount / 100
    else:  # qty
        # Assume 100g per unit if weight unknown
        if product.weight_g and product.quantity:
            weight_per_unit = product.weight_g / product.quantity
        else:
            weight_per_unit = 100.0
        factor = (weight_per_unit * consume_data.amount) / 100

    calories = product.calories * factor if product.calories else 0
    protein = product.protein * factor if product.protein else 0
    fat = product.fat * factor if product.fat else 0
    carbs = product.carbs * factor if product.carbs else 0
    fiber = product.fiber * factor if product.fiber else 0

    msk_tz = pytz.timezone("Europe/Moscow")

    # Create consumption log
    log = ConsumptionLog(
        user_id=user.id,
        product_name=product.name,
        calories=calories,
        protein=protein,
        fat=fat,
        carbs=carbs,
        fiber=fiber,
        date=datetime.now(msk_tz).replace(tzinfo=None),
    )
    session.add(log)

    # Update product quantity
    if consume_data.unit == "qty":
        if product.quantity <= consume_data.amount:
            await session.delete(product)
            message = "Product finished"
        else:
            product.quantity -= consume_data.amount
            message = f"Consumed {consume_data.amount} units"
    else:  # grams
        if product.weight_g:
            if product.weight_g <= consume_data.amount:
                await session.delete(product)
                message = "Product finished"
            else:
                product.weight_g -= consume_data.amount
                message = f"Consumed {consume_data.amount}g"
        else:
            message = f"Logged {consume_data.amount}g (weight not tracked)"

    await session.commit()

    return {
        "message": message,
        "logged": {
            "calories": round(calories, 1),
            "protein": round(protein, 1),
            "fat": round(fat, 1),
            "carbs": round(carbs, 1),
            "fiber": round(fiber, 1),
        }
    }
