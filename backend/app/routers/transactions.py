from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.transaction import Transaction
from app.schemas.transaction import TransactionListItem, TransactionListResponse

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("", response_model=TransactionListResponse)
async def list_transactions(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    upload_id: int | None = Query(default=None, ge=1),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> TransactionListResponse:
    stmt: Select[tuple[Transaction]] = select(Transaction)

    if upload_id is not None:
        stmt = stmt.where(Transaction.upload_id == upload_id)
    if date_from is not None:
        stmt = stmt.where(Transaction.date >= date_from)
    if date_to is not None:
        stmt = stmt.where(Transaction.date <= date_to)

    stmt = stmt.order_by(Transaction.date.desc(), Transaction.id.desc()).offset(offset).limit(limit)

    result = await db.execute(stmt)
    transactions = result.scalars().all()

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
            )
            for tx in transactions
        ]
    )
