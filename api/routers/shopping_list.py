"""Shopping list router for FoodFlow API."""
from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from api.auth import DBSession, CurrentUser
from api.schemas import ShoppingListItemCreate, ShoppingListItemRead
from database.models import ShoppingListItem

router = APIRouter()


@router.get("", response_model=list[ShoppingListItemRead])
async def list_shopping_items(user: CurrentUser, session: DBSession):
    """Get shopping list."""
    stmt = (
        select(ShoppingListItem)
        .where(ShoppingListItem.user_id == user.id)
        .order_by(ShoppingListItem.is_bought, ShoppingListItem.created_at.desc())
    )
    items = (await session.execute(stmt)).scalars().all()
    return [ShoppingListItemRead.model_validate(item) for item in items]


@router.post("", response_model=ShoppingListItemRead, status_code=201)
async def add_shopping_item(data: ShoppingListItemCreate, user: CurrentUser, session: DBSession):
    """Add item to shopping list."""
    item = ShoppingListItem(
        user_id=user.id,
        product_name=data.product_name,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return ShoppingListItemRead.model_validate(item)


@router.put("/{item_id}/buy")
async def mark_bought(item_id: int, user: CurrentUser, session: DBSession):
    """Mark item as bought."""
    item = await session.get(ShoppingListItem, item_id)
    if not item or item.user_id != user.id:
        raise HTTPException(status_code=404, detail="Item not found")
    
    item.is_bought = True
    await session.commit()
    return {"message": "Marked as bought"}


@router.put("/{item_id}/unbuy")
async def mark_unbought(item_id: int, user: CurrentUser, session: DBSession):
    """Mark item as not bought."""
    item = await session.get(ShoppingListItem, item_id)
    if not item or item.user_id != user.id:
        raise HTTPException(status_code=404, detail="Item not found")
    
    item.is_bought = False
    await session.commit()
    return {"message": "Marked as not bought"}


@router.delete("/{item_id}", status_code=204)
async def delete_shopping_item(item_id: int, user: CurrentUser, session: DBSession):
    """Delete shopping list item."""
    item = await session.get(ShoppingListItem, item_id)
    if not item or item.user_id != user.id:
        raise HTTPException(status_code=404, detail="Item not found")
    
    await session.delete(item)
    await session.commit()
