from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.category import Category
from app.models.merchant import Merchant
from app.models.transaction import Transaction
from app.schemas.merchant import (
    MerchantListItem,
    MerchantListResponse,
    MerchantUpdateRequest,
    MerchantUpdateResponse,
)

router = APIRouter(prefix="/merchants", tags=["merchants"])


@router.get("", response_model=MerchantListResponse)
async def list_merchants(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> MerchantListResponse:
    total_spent_expr = func.coalesce(
        func.sum(
            case(
                (Transaction.direction == "expense", Transaction.amount_gel),
                else_=0,
            )
        ),
        0,
    )

    stmt = (
        select(
            Merchant.id,
            Merchant.raw_name,
            Merchant.normalized_name,
            Merchant.category,
            Merchant.category_source,
            Merchant.mcc_code,
            func.count(Transaction.id).label("transaction_count"),
            total_spent_expr.label("total_spent"),
        )
        .outerjoin(Transaction, Transaction.merchant_id == Merchant.id)
        .group_by(Merchant.id)
        .order_by(total_spent_expr.desc(), Merchant.id.asc())
        .offset(offset)
        .limit(limit)
    )

    rows = (await db.execute(stmt)).all()
    return MerchantListResponse(
        items=[
            MerchantListItem(
                id=row.id,
                raw_name=row.raw_name,
                normalized_name=row.normalized_name,
                category=row.category,
                category_source=row.category_source,
                mcc_code=row.mcc_code,
                transaction_count=row.transaction_count,
                total_spent=Decimal(str(row.total_spent)),
            )
            for row in rows
        ]
    )


@router.patch("/{merchant_id}", response_model=MerchantUpdateResponse)
async def update_merchant_category(
    merchant_id: int,
    payload: MerchantUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> MerchantUpdateResponse:
    merchant = await db.get(Merchant, merchant_id)
    if merchant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Merchant not found")

    category_name = payload.category.strip()
    category_exists = await db.scalar(
        select(func.count()).select_from(Category).where(Category.name == category_name)
    )
    if not category_exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unknown category. Seed categories first or use an existing category name.",
        )

    merchant.category = category_name
    merchant.category_source = "user"
    await db.commit()
    await db.refresh(merchant)

    return MerchantUpdateResponse(
        id=merchant.id,
        category=merchant.category,
        category_source=merchant.category_source,
    )
