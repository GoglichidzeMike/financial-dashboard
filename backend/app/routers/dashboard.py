from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.merchant import Merchant
from app.models.transaction import Transaction
from app.schemas.dashboard import (
    CurrencyBreakdownItem,
    CurrencyBreakdownResponse,
    DashboardSummaryResponse,
    MonthlyTrendItem,
    MonthlyTrendResponse,
    SpendingByCategoryItem,
    SpendingByCategoryResponse,
    TopMerchantItem,
    TopMerchantsResponse,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _apply_date_filter(stmt, date_from: date | None, date_to: date | None):
    if date_from is not None:
        stmt = stmt.where(Transaction.date >= date_from)
    if date_to is not None:
        stmt = stmt.where(Transaction.date <= date_to)
    return stmt


@router.get("/summary", response_model=DashboardSummaryResponse)
async def dashboard_summary(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> DashboardSummaryResponse:
    spent_expr = func.coalesce(
        func.sum(case((Transaction.direction == "expense", Transaction.amount_gel), else_=0)),
        0,
    )
    income_expr = func.coalesce(
        func.sum(case((Transaction.direction == "income", Transaction.amount_gel), else_=0)),
        0,
    )
    expense_count_expr = func.coalesce(
        func.sum(case((Transaction.direction == "expense", 1), else_=0)),
        0,
    )

    stmt = select(spent_expr, income_expr, expense_count_expr).select_from(Transaction)
    stmt = _apply_date_filter(stmt, date_from, date_to)
    row = (await db.execute(stmt)).one()

    total_spent = float(row[0] or 0)
    total_income = float(row[1] or 0)

    return DashboardSummaryResponse(
        total_spent_gel=total_spent,
        total_income_gel=total_income,
        net_cash_flow_gel=round(total_income - total_spent, 2),
        expense_transaction_count=int(row[2] or 0),
    )


@router.get("/spending-by-category", response_model=SpendingByCategoryResponse)
async def spending_by_category(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> SpendingByCategoryResponse:
    category_expr = func.coalesce(Merchant.category, "Other")

    stmt = (
        select(
            category_expr.label("category"),
            func.coalesce(func.sum(Transaction.amount_gel), 0).label("amount_gel"),
            func.count(Transaction.id).label("transaction_count"),
        )
        .outerjoin(Merchant, Merchant.id == Transaction.merchant_id)
        .where(Transaction.direction == "expense")
        .group_by(category_expr)
        .order_by(func.sum(Transaction.amount_gel).desc())
    )

    stmt = _apply_date_filter(stmt, date_from, date_to)
    rows = (await db.execute(stmt)).all()

    return SpendingByCategoryResponse(
        items=[
            SpendingByCategoryItem(
                category=row.category,
                amount_gel=float(row.amount_gel or 0),
                transaction_count=int(row.transaction_count or 0),
            )
            for row in rows
        ]
    )


@router.get("/monthly-trend", response_model=MonthlyTrendResponse)
async def monthly_trend(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> MonthlyTrendResponse:
    month_expr = func.to_char(func.date_trunc("month", Transaction.date), "YYYY-MM")

    stmt = (
        select(
            month_expr.label("month"),
            func.coalesce(func.sum(Transaction.amount_gel), 0).label("amount_gel"),
        )
        .where(Transaction.direction == "expense")
        .group_by(month_expr)
        .order_by(month_expr.asc())
    )
    stmt = _apply_date_filter(stmt, date_from, date_to)
    rows = (await db.execute(stmt)).all()

    return MonthlyTrendResponse(
        items=[
            MonthlyTrendItem(month=row.month, amount_gel=float(row.amount_gel or 0))
            for row in rows
        ]
    )


@router.get("/top-merchants", response_model=TopMerchantsResponse)
async def top_merchants(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> TopMerchantsResponse:
    merchant_name_expr = func.coalesce(Merchant.normalized_name, "Unknown")

    stmt = (
        select(
            Merchant.id.label("merchant_id"),
            merchant_name_expr.label("merchant_name"),
            func.coalesce(func.sum(Transaction.amount_gel), 0).label("amount_gel"),
            func.count(Transaction.id).label("transaction_count"),
        )
        .outerjoin(Merchant, Merchant.id == Transaction.merchant_id)
        .where(Transaction.direction == "expense")
        .group_by(Merchant.id, merchant_name_expr)
        .order_by(func.sum(Transaction.amount_gel).desc())
        .limit(limit)
    )
    stmt = _apply_date_filter(stmt, date_from, date_to)
    rows = (await db.execute(stmt)).all()

    return TopMerchantsResponse(
        items=[
            TopMerchantItem(
                merchant_id=row.merchant_id,
                merchant_name=row.merchant_name,
                amount_gel=float(row.amount_gel or 0),
                transaction_count=int(row.transaction_count or 0),
            )
            for row in rows
        ]
    )


@router.get("/currency-breakdown", response_model=CurrencyBreakdownResponse)
async def currency_breakdown(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> CurrencyBreakdownResponse:
    stmt = (
        select(
            Transaction.currency_original.label("currency"),
            func.coalesce(func.sum(Transaction.amount_original), 0).label("amount_original"),
            func.count(Transaction.id).label("transaction_count"),
        )
        .where(Transaction.direction == "expense")
        .group_by(Transaction.currency_original)
        .order_by(func.sum(Transaction.amount_original).desc())
    )
    stmt = _apply_date_filter(stmt, date_from, date_to)
    rows = (await db.execute(stmt)).all()

    return CurrencyBreakdownResponse(
        items=[
            CurrencyBreakdownItem(
                currency=row.currency,
                amount_original=float(row.amount_original or 0),
                transaction_count=int(row.transaction_count or 0),
            )
            for row in rows
        ]
    )
