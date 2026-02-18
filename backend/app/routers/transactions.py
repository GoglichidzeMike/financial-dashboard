from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Select, String, asc, cast, delete, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Literal

from app.db import get_db
from app.models.merchant import Merchant
from app.models.transaction import Transaction
from app.schemas.transaction import TransactionListItem, TransactionListMeta, TransactionListResponse

router = APIRouter(prefix="/transactions", tags=["transactions"])


def _apply_filters(
    stmt: Select,
    *,
    upload_id: int | None,
    date_from: date | None,
    date_to: date | None,
    direction: Literal["expense", "income", "transfer"] | None,
    category: str | None,
    categories: list[str] | None,
    merchant: str | None,
    currency_original: str | None,
    amount_gel_min: float | None,
    amount_gel_max: float | None,
) -> Select:
    if upload_id is not None:
        stmt = stmt.where(Transaction.upload_id == upload_id)
    if date_from is not None:
        stmt = stmt.where(Transaction.date >= date_from)
    if date_to is not None:
        stmt = stmt.where(Transaction.date <= date_to)
    if direction is not None:
        stmt = stmt.where(Transaction.direction == direction)
    if categories:
        stmt = stmt.where(func.coalesce(Merchant.category, "Other").in_(categories))
    elif category:
        stmt = stmt.where(func.coalesce(Merchant.category, "Other") == category)
    if merchant:
        term = f"%{merchant.strip()}%"
        stmt = stmt.where(
            or_(
                Merchant.normalized_name.ilike(term),
                Merchant.raw_name.ilike(term),
            )
        )
    if currency_original:
        stmt = stmt.where(Transaction.currency_original == currency_original.upper())
    if amount_gel_min is not None:
        stmt = stmt.where(Transaction.amount_gel >= amount_gel_min)
    if amount_gel_max is not None:
        stmt = stmt.where(Transaction.amount_gel <= amount_gel_max)
    return stmt


@router.get("", response_model=TransactionListResponse)
async def list_transactions(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    upload_id: int | None = Query(default=None, ge=1),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    direction: Literal["expense", "income", "transfer"] | None = Query(default=None),
    category: str | None = Query(default=None),
    categories: str | None = Query(default=None),
    merchant: str | None = Query(default=None),
    currency_original: str | None = Query(default=None),
    amount_gel_min: float | None = Query(default=None),
    amount_gel_max: float | None = Query(default=None),
    sort_by: Literal[
        "date",
        "amount_gel",
        "amount_original",
        "merchant",
        "category",
        "direction",
    ] = Query(default="date"),
    sort_order: Literal["asc", "desc"] = Query(default="desc"),
    db: AsyncSession = Depends(get_db),
) -> TransactionListResponse:
    parsed_categories = (
        [value.strip() for value in categories.split(",") if value.strip()]
        if categories
        else None
    )

    merchant_name_expr = func.coalesce(Merchant.normalized_name, "Unknown").label("merchant_name")
    category_expr = func.coalesce(Merchant.category, "Other").label("category")

    stmt: Select = (
        select(Transaction, merchant_name_expr, category_expr)
        .outerjoin(Merchant, Merchant.id == Transaction.merchant_id)
    )

    stmt = _apply_filters(
        stmt,
        upload_id=upload_id,
        date_from=date_from,
        date_to=date_to,
        direction=direction,
        category=category,
        categories=parsed_categories,
        merchant=merchant,
        currency_original=currency_original,
        amount_gel_min=amount_gel_min,
        amount_gel_max=amount_gel_max,
    )

    sortable_columns = {
        "date": Transaction.date,
        "amount_gel": Transaction.amount_gel,
        "amount_original": Transaction.amount_original,
        "merchant": cast(func.coalesce(Merchant.normalized_name, "Unknown"), String),
        "category": cast(func.coalesce(Merchant.category, "Other"), String),
        "direction": cast(Transaction.direction, String),
    }
    sort_column = sortable_columns[sort_by]
    primary_order = asc(sort_column) if sort_order == "asc" else desc(sort_column)

    count_stmt = select(func.count(Transaction.id)).select_from(Transaction).outerjoin(
        Merchant, Merchant.id == Transaction.merchant_id
    )
    count_stmt = _apply_filters(
        count_stmt,
        upload_id=upload_id,
        date_from=date_from,
        date_to=date_to,
        direction=direction,
        category=category,
        categories=parsed_categories,
        merchant=merchant,
        currency_original=currency_original,
        amount_gel_min=amount_gel_min,
        amount_gel_max=amount_gel_max,
    )
    total = int((await db.execute(count_stmt)).scalar_one() or 0)

    stmt = stmt.order_by(primary_order, Transaction.id.desc()).offset(offset).limit(limit)

    result = await db.execute(stmt)
    rows = result.all()

    return TransactionListResponse(
        items=[
            TransactionListItem(
                id=tx.id,
                date=tx.date,
                posted_date=tx.posted_date,
                description_raw=tx.description_raw,
                direction=tx.direction,
                amount_original=tx.amount_original,
                currency_original=tx.currency_original,
                amount_gel=tx.amount_gel,
                conversion_rate=tx.conversion_rate,
                card_last4=tx.card_last4,
                mcc_code=tx.mcc_code,
                upload_id=tx.upload_id,
                merchant_name=merchant_name,
                category=category_name,
            )
            for tx, merchant_name, category_name in rows
        ],
        meta=TransactionListMeta(
            total=total,
            limit=limit,
            offset=offset,
            has_next=(offset + limit) < total,
        ),
    )


@router.delete("/{transaction_id}")
async def delete_transaction(
    transaction_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    stmt = delete(Transaction).where(Transaction.id == transaction_id)
    result = await db.execute(stmt)
    if (result.rowcount or 0) == 0:
        raise HTTPException(status_code=404, detail="Transaction not found")
    await db.commit()
    return {"status": "deleted"}
