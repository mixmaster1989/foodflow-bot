"""Saved dishes router for FoodFlow API."""
from datetime import datetime

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from api.auth import CurrentUser, DBSession
from api.schemas import SavedDishCreate, SavedDishLog, SavedDishRead
from database.models import SavedDish, Product

router = APIRouter()


@router.get("/", response_model=list[SavedDishRead])
async def list_saved_dishes(
    user: CurrentUser,
    session: DBSession,
):
    """List all saved dishes/templates for the current user."""
    stmt = select(SavedDish).where(SavedDish.user_id == user.id).order_by(SavedDish.id.desc())
    dishes = (await session.execute(stmt)).scalars().all()
    return dishes


@router.post("/", response_model=SavedDishRead)
async def create_saved_dish(
    dish: SavedDishCreate,
    user: CurrentUser,
    session: DBSession,
):
    """Save a new meal template."""
    # Convert Pydantic models to dicts for JSON storage
    components_dicts = [comp.model_dump() for comp in dish.components]
    
    new_dish = SavedDish(
        user_id=user.id,
        name=dish.name,
        dish_type=dish.dish_type,
        components=components_dicts,
        total_calories=dish.total_calories,
        total_protein=dish.total_protein,
        total_fat=dish.total_fat,
        total_carbs=dish.total_carbs,
        total_fiber=dish.total_fiber,
    )
    
    session.add(new_dish)
    await session.commit()
    await session.refresh(new_dish)
    return new_dish


@router.delete("/{dish_id}")
async def delete_saved_dish(
    dish_id: int,
    user: CurrentUser,
    session: DBSession,
):
    """Delete a saved dish template."""
    dish = await session.get(SavedDish, dish_id)
    if not dish or dish.user_id != user.id:
        raise HTTPException(status_code=404, detail="Saved dish not found")
        
    await session.delete(dish)
    await session.commit()
    return {"message": "Saved dish deleted successfully"}


@router.post("/{dish_id}/log")
async def log_saved_dish(
    dish_id: int,
    log_req: SavedDishLog,
    user: CurrentUser,
    session: DBSession,
):
    """Log a saved dish directly to the user's consumption diary."""
    dish = await session.get(SavedDish, dish_id)
    if not dish or dish.user_id != user.id:
        raise HTTPException(status_code=404, detail="Saved dish not found")
        
    target_date = datetime.now()
    if log_req.date:
        try:
            target_date = datetime.fromisoformat(log_req.date.replace('Z', '+00:00'))
        except ValueError:
            pass # Keep default now
            
    # Add products
    for comp in dish.components:
        prod = Product(
            user_id=user.id,
            name=comp.get("name"),
            calories=comp.get("calories", 0),
            protein=comp.get("protein", 0),
            fat=comp.get("fat", 0),
            carbs=comp.get("carbs", 0),
            fiber=comp.get("fiber", 0),
            category="custom",
            source="saved_dish",
            price=0,
            quantity=comp.get("weight_g", 1), # store weight if available
            created_at=target_date,
        )
        session.add(prod)
        
    await session.commit()
    return {"message": "Saved dish logged successfully"}
