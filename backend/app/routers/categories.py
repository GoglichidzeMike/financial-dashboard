from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.category import Category
from app.schemas.category import CategoryListResponse

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=CategoryListResponse)
async def list_categories(db: AsyncSession = Depends(get_db)) -> CategoryListResponse:
    names = (await db.execute(select(Category.name).order_by(Category.name.asc()))).scalars().all()
    return CategoryListResponse(items=list(names))
