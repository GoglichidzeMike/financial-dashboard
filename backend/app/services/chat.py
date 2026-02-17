from __future__ import annotations

import calendar
import json
import re
from dataclasses import dataclass
from datetime import date

from openai import AsyncOpenAI
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.merchant import Merchant
from app.models.transaction import Transaction
from app.schemas.chat import ChatHistoryTurn, ChatResponse, ChatSource

MONTH_NAME_TO_NUMBER = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

CATEGORY_ALIASES = {
    "utilities": ["Utilities"],
    "utility": ["Utilities"],
    "grocery": ["Groceries"],
    "groceries": ["Groceries"],
    "food": ["Dining & Restaurants", "Food Delivery"],
    "delivery": ["Food Delivery"],
    "transport": ["Transport & Taxi", "Fuel", "Parking"],
    "taxi": ["Transport & Taxi"],
    "subscriptions": ["Subscriptions"],
    "subscription": ["Subscriptions"],
    "shopping": ["Shopping & Clothing", "Online Shopping"],
    "pharmacy": ["Pharmacy & Health"],
    "health": ["Pharmacy & Health"],
    "travel": ["Travel & Flights"],
    "income": ["Income & Transfers"],
    "transfer": ["Income & Transfers"],
}


@dataclass
class IntentPlan:
    intent: str
    category_filters: list[str]
    merchant_hint: str | None
    compare_periods: bool
    wants_semantic: bool


def _llm_available() -> bool:
    key = settings.OPENAI_API_KEY.strip()
    return bool(key and key != "sk-your-key-here")


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def _extract_month_year_pairs(question: str) -> list[tuple[int, int]]:
    lowered = question.lower()
    pairs: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for month_name, year in re.findall(
        r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{4})\b",
        lowered,
    ):
        pair = (int(year), MONTH_NAME_TO_NUMBER[month_name])
        if pair not in seen:
            pairs.append(pair)
            seen.add(pair)
    return pairs


def _extract_category_filters(question: str) -> list[str]:
    lowered = question.lower()
    categories: list[str] = []
    seen: set[str] = set()
    for alias, mapped in CATEGORY_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", lowered):
            for category in mapped:
                if category not in seen:
                    categories.append(category)
                    seen.add(category)
    return categories


def _looks_referential(question: str) -> bool:
    lowered = question.lower()
    hints = ["that", "those", "it", "same", "again", "also", "too", "there", "this"]
    return any(re.search(rf"\b{re.escape(hint)}\b", lowered) for hint in hints)


def _merge_question_with_history(question: str, history: list[ChatHistoryTurn]) -> str:
    if not history:
        return question
    if not _looks_referential(question):
        return question
    last_question = history[-1].question.strip()
    if not last_question:
        return question
    return f"Previous user context: {last_question}\nCurrent user question: {question}"


def _extract_merchant_hint(question: str) -> str | None:
    lowered = question.lower().strip()
    patterns = [
        r"how has\s+(.+?)\s+changed",
        r"compare\s+(.+?)\s+(?:from|between|to)",
        r"top merchant[s]?\s+(?:for|in|is)\s+(.+)",
        r"merchant\s+(.+?)\s+(?:this month|last month|in)",
    ]
    for pattern in patterns:
        match = re.search(pattern, lowered)
        if match:
            candidate = match.group(1).strip(" ?.,")
            if candidate:
                return candidate
    return None


def _infer_date_range_from_question(
    question: str, date_from: date | None, date_to: date | None
) -> tuple[date | None, date | None]:
    lowered = question.lower()
    if "last month" in lowered and "this month" in lowered:
        return None, None
    if date_from is not None or date_to is not None:
        return date_from, date_to

    explicit = _extract_month_year_pairs(question)
    today = date.today()
    if len(explicit) == 1 and re.search(r"\b(from|starting from|since)\b", lowered):
        year, month = explicit[0]
        start, _ = _month_bounds(year, month)
        if re.search(r"\b(today|now|to date|up to today|until today)\b", lowered):
            return start, today

    if len(explicit) == 1:
        year, month = explicit[0]
        return _month_bounds(year, month)

    if "this month" in lowered:
        return _month_bounds(today.year, today.month)
    if "last month" in lowered:
        if today.month == 1:
            return _month_bounds(today.year - 1, 12)
        return _month_bounds(today.year, today.month - 1)
    return None, None


def _pct_change(from_value: float, to_value: float) -> str:
    if abs(from_value) < 1e-9:
        return "n/a"
    pct = ((to_value - from_value) / from_value) * 100
    return f"{pct:.2f}%"


def _apply_base_filters(
    stmt,
    *,
    date_from: date | None,
    date_to: date | None,
    direction: str | None = None,
    category_filters: list[str] | None = None,
    merchant_hint: str | None = None,
):
    stmt = stmt.outerjoin(Merchant, Merchant.id == Transaction.merchant_id)
    if date_from is not None:
        stmt = stmt.where(Transaction.date >= date_from)
    if date_to is not None:
        stmt = stmt.where(Transaction.date <= date_to)
    if direction is not None:
        stmt = stmt.where(Transaction.direction == direction)
    if category_filters:
        stmt = stmt.where(Merchant.category.in_(category_filters))
    if merchant_hint:
        stmt = stmt.where(Merchant.normalized_name.ilike(f"%{merchant_hint}%"))
    return stmt


def _filter_label(
    *,
    date_from: date | None,
    date_to: date | None,
    category_filters: list[str] | None,
    merchant_hint: str | None,
) -> str:
    parts: list[str] = []
    if date_from or date_to:
        parts.append(f"date={date_from or '*'}..{date_to or '*'}")
    if category_filters:
        parts.append(f"categories={','.join(category_filters)}")
    if merchant_hint:
        parts.append(f"merchant~{merchant_hint}")
    return "; ".join(parts) if parts else "no extra filters"


def _format_period_text(date_from: date | None, date_to: date | None) -> str:
    if date_from and date_to:
        return f"{date_from.isoformat()} to {date_to.isoformat()}"
    if date_from:
        return f"from {date_from.isoformat()}"
    if date_to:
        return f"until {date_to.isoformat()}"
    return "the selected period"


async def _resolve_two_months(
    db: AsyncSession,
    question: str,
    date_from: date | None,
    date_to: date | None,
) -> tuple[tuple[date, date], tuple[date, date]] | None:
    lowered = question.lower()
    explicit = _extract_month_year_pairs(question)
    if len(explicit) >= 2:
        first = _month_bounds(explicit[0][0], explicit[0][1])
        second = _month_bounds(explicit[1][0], explicit[1][1])
        return first, second

    today = date.today()
    if "last month" in lowered and "this month" in lowered:
        current = _month_bounds(today.year, today.month)
        if today.month == 1:
            previous = _month_bounds(today.year - 1, 12)
        else:
            previous = _month_bounds(today.year, today.month - 1)
        return previous, current

    month_expr = func.date_trunc("month", Transaction.date).label("month_start")
    stmt = select(month_expr).distinct().order_by(month_expr.desc()).limit(2)
    if date_from is not None:
        stmt = stmt.where(Transaction.date >= date_from)
    if date_to is not None:
        stmt = stmt.where(Transaction.date <= date_to)
    rows = (await db.execute(stmt)).all()
    months = [row.month_start.date() for row in rows]
    if len(months) < 2:
        return None
    newer = _month_bounds(months[0].year, months[0].month)
    older = _month_bounds(months[1].year, months[1].month)
    return older, newer


async def _infer_intent_with_llm(question: str) -> IntentPlan | None:
    if not _llm_available():
        return None
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Classify finance question into JSON. "
                        "Return keys: intent, category_filters, merchant_hint, compare_periods, wants_semantic. "
                        "Allowed intents: summary, top_merchants, category_breakdown, monthly_trend, "
                        "compare_months, merchant_change, category_change, category_total, transactions_search. "
                        "category_filters must be an array of canonical category names when obvious."
                    ),
                },
                {"role": "user", "content": question},
            ],
        )
        raw = (response.choices[0].message.content or "").strip()
        if not raw:
            return None
        parsed = json.loads(raw)
        intent = str(parsed.get("intent", "")).strip().lower()
        if intent not in {
            "summary",
            "top_merchants",
            "category_breakdown",
            "monthly_trend",
            "compare_months",
            "merchant_change",
            "category_change",
            "category_total",
            "transactions_search",
        }:
            return None
        raw_categories = parsed.get("category_filters", [])
        categories = [str(item).strip() for item in raw_categories if str(item).strip()]
        merchant_hint = parsed.get("merchant_hint")
        merchant_text = str(merchant_hint).strip() if merchant_hint else None
        return IntentPlan(
            intent=intent,
            category_filters=categories,
            merchant_hint=merchant_text,
            compare_periods=bool(parsed.get("compare_periods", False)),
            wants_semantic=bool(parsed.get("wants_semantic", False)),
        )
    except Exception:
        return None


def _infer_intent_heuristic(question: str) -> IntentPlan:
    lowered = question.lower()
    category_filters = _extract_category_filters(question)
    merchant_hint = _extract_merchant_hint(question)

    has_compare = "compare" in lowered or "compared" in lowered or "change" in lowered
    if merchant_hint and has_compare and "month" in lowered:
        return IntentPlan("merchant_change", category_filters, merchant_hint, True, False)
    if has_compare and ("month" in lowered or ("last month" in lowered and "this month" in lowered)):
        if "category" in lowered or "categories" in lowered:
            return IntentPlan("category_change", category_filters, None, True, False)
        return IntentPlan("compare_months", category_filters, None, True, False)
    if category_filters and any(
        phrase in lowered for phrase in ["every month", "monthly", "month breakdown", "by month"]
    ):
        return IntentPlan("monthly_trend", category_filters, None, False, False)
    if category_filters and ("how much" in lowered or "total" in lowered or "spent" in lowered):
        return IntentPlan("category_total", category_filters, None, False, False)
    if "top" in lowered and "merchant" in lowered:
        return IntentPlan("top_merchants", category_filters, merchant_hint, False, False)
    if "category" in lowered or "categories" in lowered:
        return IntentPlan("category_breakdown", category_filters, None, False, False)
    if "month" in lowered or "trend" in lowered:
        return IntentPlan("monthly_trend", category_filters, None, False, False)
    if any(word in lowered for word in ["transaction", "payment", "find", "show me", "which"]):
        return IntentPlan("transactions_search", category_filters, merchant_hint, False, True)
    return IntentPlan("summary", category_filters, merchant_hint, False, False)


async def _build_intent_plan(question: str) -> IntentPlan:
    llm_plan = await _infer_intent_with_llm(question)
    if llm_plan is not None:
        if not llm_plan.category_filters:
            llm_plan.category_filters = _extract_category_filters(question)
        if not llm_plan.merchant_hint:
            llm_plan.merchant_hint = _extract_merchant_hint(question)
        lowered = question.lower()
        if llm_plan.category_filters and any(
            phrase in lowered for phrase in ["every month", "monthly", "month breakdown", "by month"]
        ):
            llm_plan.intent = "monthly_trend"
        return llm_plan
    return _infer_intent_heuristic(question)


async def _summary_source(
    db: AsyncSession,
    *,
    date_from: date | None,
    date_to: date | None,
    category_filters: list[str],
    merchant_hint: str | None,
) -> ChatSource:
    spent_expr = func.coalesce(
        func.sum(case((Transaction.direction == "expense", Transaction.amount_gel), else_=0)),
        0,
    )
    income_expr = func.coalesce(
        func.sum(case((Transaction.direction == "income", Transaction.amount_gel), else_=0)),
        0,
    )
    count_expr = func.count(Transaction.id)
    stmt = select(
        spent_expr.label("spent"),
        income_expr.label("income"),
        count_expr.label("count"),
    ).select_from(Transaction)
    stmt = _apply_base_filters(
        stmt,
        date_from=date_from,
        date_to=date_to,
        category_filters=category_filters,
        merchant_hint=merchant_hint,
    )
    row = (await db.execute(stmt)).one()
    spent = float(row.spent or 0)
    income = float(row.income or 0)
    net = income - spent
    return ChatSource(
        source_type="sql",
        title="Summary",
        content=(
            f"- Total spend: GEL {spent:.2f}\n"
            f"- Total income: GEL {income:.2f}\n"
            f"- Net cash flow: GEL {net:.2f}\n"
            f"- Transactions: {int(row.count or 0)}\n"
            f"- Filters: {_filter_label(date_from=date_from, date_to=date_to, category_filters=category_filters, merchant_hint=merchant_hint)}"
        ),
        table_columns=["Metric", "Value"],
        table_rows=[
            ["Total spend", f"GEL {spent:.2f}"],
            ["Total income", f"GEL {income:.2f}"],
            ["Net cash flow", f"GEL {net:.2f}"],
            ["Transactions", f"{int(row.count or 0)}"],
        ],
    )


async def _category_total_sources_and_answer(
    db: AsyncSession,
    *,
    date_from: date | None,
    date_to: date | None,
    category_filters: list[str],
) -> tuple[list[ChatSource], str]:
    spent_expr = func.coalesce(func.sum(Transaction.amount_gel), 0)
    count_expr = func.count(Transaction.id)
    stmt = select(spent_expr.label("spent"), count_expr.label("count")).select_from(Transaction)
    stmt = _apply_base_filters(
        stmt,
        date_from=date_from,
        date_to=date_to,
        direction="expense",
        category_filters=category_filters,
    )
    totals = (await db.execute(stmt)).one()
    total_spend = float(totals.spent or 0)
    tx_count = int(totals.count or 0)
    avg_ticket = total_spend / tx_count if tx_count else 0

    merchant_stmt = (
        select(
            Merchant.normalized_name.label("merchant_name"),
            func.coalesce(func.sum(Transaction.amount_gel), 0).label("spend"),
            func.count(Transaction.id).label("tx_count"),
        )
        .select_from(Transaction)
    )
    merchant_stmt = _apply_base_filters(
        merchant_stmt,
        date_from=date_from,
        date_to=date_to,
        direction="expense",
        category_filters=category_filters,
    )
    merchant_stmt = merchant_stmt.group_by(Merchant.normalized_name).order_by(
        func.sum(Transaction.amount_gel).desc()
    ).limit(5)
    merchants = (await db.execute(merchant_stmt)).all()

    category_label = ", ".join(category_filters) if category_filters else "selected categories"
    period_text = _format_period_text(date_from, date_to)
    breakdown_lines = []
    for row in merchants:
        spend = float(row.spend)
        pct = (spend / total_spend * 100) if total_spend > 0 else 0
        breakdown_lines.append(
            f"- {row.merchant_name or 'unknown'}: GEL {spend:.2f} ({pct:.2f}%, {row.tx_count} tx)"
        )

    total_source = ChatSource(
        source_type="sql",
        title="Category total",
        content=(
            f"- Category: {category_label}\n"
            f"- Period: {period_text}\n"
            f"- Spend: GEL {total_spend:.2f}\n"
            f"- Transactions: {tx_count}\n"
            f"- Avg ticket: GEL {avg_ticket:.2f}\n"
            f"- Filters: {_filter_label(date_from=date_from, date_to=date_to, category_filters=category_filters, merchant_hint=None)}"
        ),
        table_columns=["Category", "Period", "Spend", "Transactions", "Avg ticket"],
        table_rows=[
            [
                category_label,
                period_text,
                f"GEL {total_spend:.2f}",
                str(tx_count),
                f"GEL {avg_ticket:.2f}",
            ]
        ],
    )
    breakdown_rows = []
    for row in merchants:
        spend = float(row.spend)
        pct = (spend / total_spend * 100) if total_spend > 0 else 0
        breakdown_rows.append(
            [row.merchant_name or "unknown", f"GEL {spend:.2f}", f"{pct:.2f}%", str(row.tx_count)]
        )
    breakdown_source = ChatSource(
        source_type="sql",
        title="Category merchant breakdown",
        content="\n".join(breakdown_lines) if breakdown_lines else "No merchant breakdown rows found.",
        table_columns=["Merchant", "Spend", "Share", "Transactions"] if breakdown_rows else None,
        table_rows=breakdown_rows or None,
    )

    answer = (
        f"In {period_text}, you spent GEL {total_spend:.2f} on {category_label} "
        f"across {tx_count} transactions (avg GEL {avg_ticket:.2f})."
    )
    if breakdown_lines:
        top_text = "; ".join(
            f"{(row.merchant_name or 'unknown')} GEL {float(row.spend):.2f}" for row in merchants[:3]
        )
        answer += f" Top contributors: {top_text}."
    return [total_source, breakdown_source], answer


async def _top_merchants_source(
    db: AsyncSession,
    *,
    date_from: date | None,
    date_to: date | None,
    category_filters: list[str],
) -> ChatSource:
    stmt = (
        select(
            Merchant.id.label("merchant_id"),
            Merchant.normalized_name.label("merchant_name"),
            func.coalesce(func.sum(Transaction.amount_gel), 0).label("spend"),
            func.count(Transaction.id).label("tx_count"),
        )
        .select_from(Transaction)
    )
    stmt = _apply_base_filters(
        stmt,
        date_from=date_from,
        date_to=date_to,
        direction="expense",
        category_filters=category_filters,
    )
    stmt = stmt.group_by(Merchant.id, Merchant.normalized_name).order_by(
        func.sum(Transaction.amount_gel).desc()
    ).limit(10)
    rows = (await db.execute(stmt)).all()

    total_stmt = select(func.coalesce(func.sum(Transaction.amount_gel), 0)).select_from(Transaction)
    total_stmt = _apply_base_filters(
        total_stmt,
        date_from=date_from,
        date_to=date_to,
        direction="expense",
        category_filters=category_filters,
    )
    total_spend = float((await db.execute(total_stmt)).scalar_one() or 0)
    if not rows:
        return ChatSource(
            source_type="sql",
            title="Top merchants",
            content=(
                "No expense rows found for this period.\n"
                f"- Filters: {_filter_label(date_from=date_from, date_to=date_to, category_filters=category_filters, merchant_hint=None)}"
            ),
        )

    lines = []
    for row in rows:
        spend = float(row.spend)
        pct = (spend / total_spend * 100) if total_spend > 0 else 0
        lines.append(f"- {row.merchant_name or 'unknown'}: GEL {spend:.2f} ({pct:.2f}% of total, {row.tx_count} tx)")
    return ChatSource(
        source_type="sql",
        title="Top merchants",
        content=(
            f"- Total spend: GEL {total_spend:.2f}\n"
            + "\n".join(lines)
            + f"\n- Filters: {_filter_label(date_from=date_from, date_to=date_to, category_filters=category_filters, merchant_hint=None)}"
        ),
        table_columns=["Merchant", "Spend", "Share", "Transactions"],
        table_rows=[
            [
                row.merchant_name or "unknown",
                f"GEL {float(row.spend):.2f}",
                f"{((float(row.spend) / total_spend * 100) if total_spend > 0 else 0):.2f}%",
                str(row.tx_count),
            ]
            for row in rows
        ],
    )


async def _category_breakdown_source(
    db: AsyncSession,
    *,
    date_from: date | None,
    date_to: date | None,
    category_filters: list[str],
) -> ChatSource:
    category_expr = func.coalesce(Merchant.category, "Other")
    stmt = select(
        category_expr.label("category"),
        func.coalesce(func.sum(Transaction.amount_gel), 0).label("spend"),
        func.count(Transaction.id).label("tx_count"),
    ).select_from(Transaction)
    stmt = _apply_base_filters(
        stmt,
        date_from=date_from,
        date_to=date_to,
        direction="expense",
        category_filters=category_filters,
    )
    stmt = stmt.group_by(category_expr).order_by(func.sum(Transaction.amount_gel).desc())
    rows = (await db.execute(stmt)).all()
    if not rows:
        return ChatSource(source_type="sql", title="Spending by category", content="No expense rows found for this period.")
    lines = [f"- {row.category}: GEL {float(row.spend):.2f} ({row.tx_count} tx)" for row in rows]
    return ChatSource(
        source_type="sql",
        title="Spending by category",
        content="\n".join(lines) + f"\n- Filters: {_filter_label(date_from=date_from, date_to=date_to, category_filters=category_filters, merchant_hint=None)}",
        table_columns=["Category", "Spend", "Transactions"],
        table_rows=[[row.category, f"GEL {float(row.spend):.2f}", str(row.tx_count)] for row in rows],
    )


async def _monthly_trend_source(
    db: AsyncSession,
    *,
    date_from: date | None,
    date_to: date | None,
    category_filters: list[str],
    merchant_hint: str | None,
) -> ChatSource:
    month_expr = func.to_char(func.date_trunc("month", Transaction.date), "YYYY-MM")
    stmt = select(
        month_expr.label("month"),
        func.coalesce(func.sum(Transaction.amount_gel), 0).label("spend"),
    ).select_from(Transaction)
    stmt = _apply_base_filters(
        stmt,
        date_from=date_from,
        date_to=date_to,
        direction="expense",
        category_filters=category_filters,
        merchant_hint=merchant_hint,
    )
    stmt = stmt.group_by(month_expr).order_by(month_expr.asc())
    rows = (await db.execute(stmt)).all()
    if not rows:
        return ChatSource(source_type="sql", title="Monthly trend", content="No monthly expense rows found for this period.")
    total = sum(float(row.spend) for row in rows)
    lines = [f"- {row.month}: GEL {float(row.spend):.2f}" for row in rows]
    lines.append(f"- Total: GEL {total:.2f}")
    return ChatSource(
        source_type="sql",
        title="Monthly trend",
        content="\n".join(lines) + f"\n- Filters: {_filter_label(date_from=date_from, date_to=date_to, category_filters=category_filters, merchant_hint=merchant_hint)}",
        table_columns=["Month", "Spend"],
        table_rows=[[row.month, f"GEL {float(row.spend):.2f}"] for row in rows]
        + [["Total", f"GEL {total:.2f}"]],
    )


async def _compare_months_source(
    db: AsyncSession,
    *,
    question: str,
    date_from: date | None,
    date_to: date | None,
    category_filters: list[str],
    merchant_hint: str | None,
) -> ChatSource:
    month_ranges = await _resolve_two_months(db, question, date_from, date_to)
    if month_ranges is None:
        return ChatSource(source_type="sql", title="Month comparison", content="Not enough monthly data to compare.")

    (first_start, _), (second_start, second_end) = month_ranges
    first_label = first_start.strftime("%Y-%m")
    second_label = second_start.strftime("%Y-%m")

    month_expr = func.to_char(func.date_trunc("month", Transaction.date), "YYYY-MM")
    spent_expr = func.coalesce(
        func.sum(case((Transaction.direction == "expense", Transaction.amount_gel), else_=0)),
        0,
    )
    income_expr = func.coalesce(
        func.sum(case((Transaction.direction == "income", Transaction.amount_gel), else_=0)),
        0,
    )
    count_expr = func.count(Transaction.id)
    stmt = select(
        month_expr.label("month"),
        spent_expr.label("spent"),
        income_expr.label("income"),
        count_expr.label("count"),
    ).select_from(Transaction)
    stmt = _apply_base_filters(
        stmt,
        date_from=first_start,
        date_to=second_end,
        category_filters=category_filters,
        merchant_hint=merchant_hint,
    )
    stmt = stmt.group_by(month_expr).order_by(month_expr.asc())
    rows = (await db.execute(stmt)).all()
    by_month = {row.month: row for row in rows}
    first = by_month.get(first_label)
    second = by_month.get(second_label)
    if first is None and second is None:
        return ChatSource(source_type="sql", title="Month comparison", content="No rows found for the compared months.")

    first_spent = float(first.spent) if first else 0.0
    first_income = float(first.income) if first else 0.0
    first_net = first_income - first_spent
    second_spent = float(second.spent) if second else 0.0
    second_income = float(second.income) if second else 0.0
    second_net = second_income - second_spent
    return ChatSource(
        source_type="sql",
        title="Month comparison",
        content=(
            f"- {first_label}: spend GEL {first_spent:.2f}, income GEL {first_income:.2f}, net GEL {first_net:.2f}, tx {int(first.count) if first else 0}\n"
            f"- {second_label}: spend GEL {second_spent:.2f}, income GEL {second_income:.2f}, net GEL {second_net:.2f}, tx {int(second.count) if second else 0}\n"
            f"- Spend change: {_pct_change(first_spent, second_spent)}\n"
            f"- Income change: {_pct_change(first_income, second_income)}\n"
            f"- Net change: {_pct_change(first_net, second_net)}\n"
            f"- Filters: {_filter_label(date_from=None, date_to=None, category_filters=category_filters, merchant_hint=merchant_hint)}"
        ),
        table_columns=["Metric", first_label, second_label, "Change"],
        table_rows=[
            ["Spend", f"GEL {first_spent:.2f}", f"GEL {second_spent:.2f}", _pct_change(first_spent, second_spent)],
            ["Income", f"GEL {first_income:.2f}", f"GEL {second_income:.2f}", _pct_change(first_income, second_income)],
            ["Net", f"GEL {first_net:.2f}", f"GEL {second_net:.2f}", _pct_change(first_net, second_net)],
            ["Transactions", str(int(first.count) if first else 0), str(int(second.count) if second else 0), "-"],
        ],
    )


async def _merchant_change_source(
    db: AsyncSession,
    *,
    question: str,
    date_from: date | None,
    date_to: date | None,
    merchant_hint: str | None,
) -> ChatSource:
    if not merchant_hint:
        return ChatSource(
            source_type="sql",
            title="Merchant month comparison",
            content="Please specify a merchant name to compare month-over-month.",
        )
    month_ranges = await _resolve_two_months(db, question, date_from, date_to)
    if month_ranges is None:
        return ChatSource(source_type="sql", title="Merchant month comparison", content="Not enough monthly data to compare.")
    (first_start, _), (second_start, second_end) = month_ranges
    first_label = first_start.strftime("%Y-%m")
    second_label = second_start.strftime("%Y-%m")
    month_expr = func.to_char(func.date_trunc("month", Transaction.date), "YYYY-MM")
    stmt = select(
        month_expr.label("month"),
        Merchant.normalized_name.label("merchant_name"),
        func.coalesce(func.sum(Transaction.amount_gel), 0).label("spend"),
    ).select_from(Transaction)
    stmt = _apply_base_filters(
        stmt,
        date_from=first_start,
        date_to=second_end,
        direction="expense",
        merchant_hint=merchant_hint,
    )
    stmt = stmt.group_by(month_expr, Merchant.normalized_name).order_by(func.sum(Transaction.amount_gel).desc())
    rows = (await db.execute(stmt)).all()
    if not rows:
        return ChatSource(
            source_type="sql",
            title="Merchant month comparison",
            content=f"No expense rows found for merchant hint '{merchant_hint}'.",
        )
    by_month = {row.month: float(row.spend) for row in rows}
    first_spend = by_month.get(first_label, 0.0)
    second_spend = by_month.get(second_label, 0.0)
    delta = second_spend - first_spend
    best_name = rows[0].merchant_name or merchant_hint
    return ChatSource(
        source_type="sql",
        title="Merchant month comparison",
        content=(
            f"- Merchant: {best_name}\n"
            f"- {first_label}: GEL {first_spend:.2f}\n"
            f"- {second_label}: GEL {second_spend:.2f}\n"
            f"- Delta: GEL {delta:.2f}\n"
            f"- Percent change: {_pct_change(first_spend, second_spend)}"
        ),
        table_columns=["Merchant", first_label, second_label, "Delta", "Percent change"],
        table_rows=[
            [
                best_name,
                f"GEL {first_spend:.2f}",
                f"GEL {second_spend:.2f}",
                f"GEL {delta:.2f}",
                _pct_change(first_spend, second_spend),
            ]
        ],
    )


async def _category_change_source(
    db: AsyncSession,
    *,
    question: str,
    date_from: date | None,
    date_to: date | None,
    category_filters: list[str],
) -> ChatSource:
    month_ranges = await _resolve_two_months(db, question, date_from, date_to)
    if month_ranges is None:
        return ChatSource(source_type="sql", title="Category month-over-month", content="Not enough monthly data to compare categories.")
    (first_start, _), (second_start, second_end) = month_ranges
    first_label = first_start.strftime("%Y-%m")
    second_label = second_start.strftime("%Y-%m")
    month_expr = func.to_char(func.date_trunc("month", Transaction.date), "YYYY-MM")
    category_expr = func.coalesce(Merchant.category, "Other")
    stmt = select(
        month_expr.label("month"),
        category_expr.label("category"),
        func.coalesce(func.sum(Transaction.amount_gel), 0).label("spend"),
    ).select_from(Transaction)
    stmt = _apply_base_filters(
        stmt,
        date_from=first_start,
        date_to=second_end,
        direction="expense",
        category_filters=category_filters,
    )
    stmt = stmt.group_by(month_expr, category_expr)
    rows = (await db.execute(stmt)).all()
    if not rows:
        return ChatSource(source_type="sql", title="Category month-over-month", content="No category rows found for the compared months.")

    by_category: dict[str, dict[str, float]] = {}
    for row in rows:
        bucket = by_category.setdefault(row.category, {first_label: 0.0, second_label: 0.0})
        bucket[row.month] = float(row.spend)
    deltas: list[tuple[str, float, float, float]] = []
    for category, spends in by_category.items():
        first_spend = spends.get(first_label, 0.0)
        second_spend = spends.get(second_label, 0.0)
        deltas.append((category, first_spend, second_spend, second_spend - first_spend))
    deltas.sort(key=lambda item: item[3], reverse=True)
    lines = []
    for category, first_spend, second_spend, delta in deltas[:10]:
        lines.append(
            f"- {category}: {first_label} GEL {first_spend:.2f} -> {second_label} GEL {second_spend:.2f} | delta GEL {delta:.2f} | pct {_pct_change(first_spend, second_spend)}"
        )
    return ChatSource(
        source_type="sql",
        title="Category month-over-month",
        content="\n".join(lines),
        table_columns=["Category", first_label, second_label, "Delta", "Percent"],
        table_rows=[
            [
                category,
                f"GEL {first_spend:.2f}",
                f"GEL {second_spend:.2f}",
                f"GEL {delta:.2f}",
                _pct_change(first_spend, second_spend),
            ]
            for category, first_spend, second_spend, delta in deltas[:10]
        ],
    )


async def _semantic_context(
    db: AsyncSession,
    question: str,
    date_from: date | None,
    date_to: date | None,
    top_k: int,
    *,
    category_filters: list[str],
    merchant_hint: str | None,
) -> list[ChatSource]:
    if not _llm_available():
        return []
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    embedding_response = await client.embeddings.create(model="text-embedding-3-small", input=question)
    query_vector = embedding_response.data[0].embedding
    distance_expr = Transaction.embedding.cosine_distance(query_vector)
    stmt = select(
        Transaction.date,
        Transaction.description_raw,
        Transaction.direction,
        Transaction.amount_gel,
        func.coalesce(Merchant.normalized_name, "unknown").label("merchant"),
        distance_expr.label("distance"),
    ).select_from(Transaction)
    stmt = _apply_base_filters(
        stmt,
        date_from=date_from,
        date_to=date_to,
        category_filters=category_filters,
        merchant_hint=merchant_hint,
    )
    stmt = stmt.where(Transaction.embedding.is_not(None)).order_by(distance_expr.asc()).limit(top_k)
    rows = (await db.execute(stmt)).all()
    if not rows:
        return []
    lines = [
        f"- {row.date} | {row.merchant} | {row.direction} | GEL {float(row.amount_gel):.2f} | {row.description_raw[:180]}"
        for row in rows
    ]
    return [ChatSource(source_type="semantic", title="Relevant transactions", content="\n".join(lines))]


def _fallback_answer(question: str, sources: list[ChatSource]) -> str:
    if not sources:
        return "I could not find relevant data to answer that question yet."
    if len(sources) == 1:
        return sources[0].content
    intro = "Here is the data-backed result."
    blocks = "\n\n".join(f"{src.title}:\n{src.content}" for src in sources)
    return f"{intro}\n\nQuestion: {question}\n\n{blocks}"


async def answer_chat(
    db: AsyncSession,
    question: str,
    date_from: date | None,
    date_to: date | None,
    top_k: int,
    history: list[ChatHistoryTurn] | None = None,
) -> ChatResponse:
    history = history or []
    merged_question = _merge_question_with_history(question, history)
    effective_date_from, effective_date_to = _infer_date_range_from_question(
        merged_question, date_from, date_to
    )
    plan = await _build_intent_plan(merged_question)

    if not plan.category_filters and history:
        for turn in reversed(history):
            inferred = _extract_category_filters(turn.question)
            if inferred:
                plan.category_filters = inferred
                break
    if not plan.merchant_hint and history:
        for turn in reversed(history):
            inferred = _extract_merchant_hint(turn.question)
            if inferred:
                plan.merchant_hint = inferred
                break

    sources: list[ChatSource] = []
    override_answer: str | None = None
    if plan.intent == "top_merchants":
        sources.append(
            await _top_merchants_source(
                db, date_from=effective_date_from, date_to=effective_date_to, category_filters=plan.category_filters
            )
        )
        mode = "sql"
    elif plan.intent == "category_breakdown":
        sources.append(
            await _category_breakdown_source(
                db, date_from=effective_date_from, date_to=effective_date_to, category_filters=plan.category_filters
            )
        )
        mode = "sql"
    elif plan.intent == "monthly_trend":
        sources.append(
            await _monthly_trend_source(
                db,
                date_from=effective_date_from,
                date_to=effective_date_to,
                category_filters=plan.category_filters,
                merchant_hint=plan.merchant_hint,
            )
        )
        mode = "sql"
    elif plan.intent == "compare_months":
        sources.append(
            await _compare_months_source(
                db,
                question=merged_question,
                date_from=effective_date_from,
                date_to=effective_date_to,
                category_filters=plan.category_filters,
                merchant_hint=plan.merchant_hint,
            )
        )
        mode = "sql"
    elif plan.intent == "merchant_change":
        sources.append(
            await _merchant_change_source(
                db,
                question=merged_question,
                date_from=effective_date_from,
                date_to=effective_date_to,
                merchant_hint=plan.merchant_hint,
            )
        )
        mode = "sql"
    elif plan.intent == "category_change":
        sources.append(
            await _category_change_source(
                db,
                question=merged_question,
                date_from=effective_date_from,
                date_to=effective_date_to,
                category_filters=plan.category_filters,
            )
        )
        mode = "sql"
    elif plan.intent == "category_total":
        category_sources, override_answer = await _category_total_sources_and_answer(
            db,
            date_from=effective_date_from,
            date_to=effective_date_to,
            category_filters=plan.category_filters,
        )
        sources.extend(category_sources)
        # Add summary as supporting source for transparency.
        sources.append(
            await _summary_source(
                db,
                date_from=effective_date_from,
                date_to=effective_date_to,
                category_filters=plan.category_filters,
                merchant_hint=None,
            )
        )
        mode = "sql"
    else:
        sources.append(
            await _summary_source(
                db,
                date_from=effective_date_from,
                date_to=effective_date_to,
                category_filters=plan.category_filters,
                merchant_hint=plan.merchant_hint,
            )
        )
        mode = "sql"

    if plan.wants_semantic or plan.intent == "transactions_search":
        try:
            sources.extend(
                await _semantic_context(
                    db,
                    merged_question,
                    effective_date_from,
                    effective_date_to,
                    top_k,
                    category_filters=plan.category_filters,
                    merchant_hint=plan.merchant_hint,
                )
            )
            mode = "mixed" if sources else mode
        except Exception:
            pass

    if plan.intent != "transactions_search":
        return ChatResponse(
            mode=mode,
            answer=override_answer or _fallback_answer(question, sources),
            sources=sources,
        )

    if not _llm_available():
        return ChatResponse(mode=mode, answer=_fallback_answer(question, sources), sources=sources)

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    context_payload = [{"source_type": s.source_type, "title": s.title, "content": s.content} for s in sources]
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.1,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a finance assistant. Use only provided context. "
                        "Never claim data is missing if source already includes totals. "
                        "Keep answers concise and numeric."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {"question": question, "merged_question": merged_question, "context": context_payload},
                        ensure_ascii=False,
                    ),
                },
            ],
        )
        answer = (response.choices[0].message.content or "").strip() or _fallback_answer(question, sources)
    except Exception:
        answer = _fallback_answer(question, sources)
    return ChatResponse(mode=mode, answer=answer, sources=sources)
