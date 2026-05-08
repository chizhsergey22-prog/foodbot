from __future__ import annotations
from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from db.models import Category, MenuItem
from dependencies import CurrentUser, DbSession

router = APIRouter(prefix="/menu", tags=["menu"])


class MenuItemOut(BaseModel):
    id: int
    name: str
    description: str | None
    price: float
    photo_url: str | None
    category_id: int | None
    category_name: str | None

    model_config = {"from_attributes": True}


class CategoryOut(BaseModel):
    id: int
    name: str
    sort_order: int
    items: list[MenuItemOut]


@router.get("/", response_model=list[CategoryOut])
async def get_menu(user: CurrentUser, session: DbSession):
    """Возвращает меню, сгруппированное по категориям (без стоп-листа)."""
    res = await session.execute(
        select(Category)
        .where(Category.is_active == True)
        .options(selectinload(Category.items))
        .order_by(Category.sort_order)
    )
    categories = res.scalars().all()

    result = []
    for cat in categories:
        items = [
            MenuItemOut(
                id=i.id,
                name=i.name,
                description=i.description,
                price=float(i.price),
                photo_url=i.photo_url,
                category_id=i.category_id,
                category_name=cat.name,
            )
            for i in cat.items
            if i.is_active
        ]
        if items:
            result.append(CategoryOut(id=cat.id, name=cat.name, sort_order=cat.sort_order, items=items))

    return result
