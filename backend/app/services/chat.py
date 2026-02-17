from __future__ import annotations

import calendar
import json
import re
from datetime import date
from typing import Any

from openai import AsyncOpenAI
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.merchant import Merchant
from app.models.transaction import Transaction
from app.schemas.chat import ChatResponse, ChatSource

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


def _llm_available() -> bool:
    key = settings.OPENAI_API_KEY.strip()
    return bool(key and key != "sk-your-key-here")


def _apply_date_filter(stmt, date_from: date | None, date_to: date | None):
    if date_from is not None:
        stmt = stmt.where(Transaction.date >= date_from)
    if date_to is not None:
        stmt = stmt.where(Transaction.date <= date_to)
    return stmt


def _question_wants_sql(question: str) -> bool:
    lowered = question.lower()
    sql_terms = [
        "how much",
        "total",
        "spent",
        "spend",
        "top",
        "category",
        "categories",
        "month",
        "trend",
        "summary",
        "breakdown",
        "income",
        "expenses",
    ]
    return any(term in lowered for term in sql_terms)


def _question_wants_semantic(question: str) -> bool:
    lowered = question.lower()
    semantic_terms = [
        "which",
        "show",
        "transaction",
        "payment",
        "where",
        "why",
        "find",
        "did i",
    ]
    return any(term in lowered for term in semantic_terms)


def _is_aggregate_question(question: str) -> bool:
    lowered = question.lower()
    aggregate_terms = [
        "top merchants",
        "top merchant",
        "compare",
        "month",
        "category",
        "breakdown",
        "%",
        "percent",
        "trend",
        "summary",
    ]
    return any(term in lowered for term in aggregate_terms)


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


def _infer_date_range_from_question(
    question: str, date_from: date | None, date_to: date | None
) -> tuple[date | None, date | None]:
    lowered = question.lower()
    if "last month" in lowered and "this month" in lowered:
        return None, None

    if date_from is not None or date_to is not None:
        return date_from, date_to

    explicit = _extract_month_year_pairs(question)

    if len(explicit) == 1:
        year, month = explicit[0]
        return _month_bounds(year, month)

    today = date.today()
    if "this month" in lowered:
        return _month_bounds(today.year, today.month)

    if "last month" in lowered:
        if today.month == 1:
            return _month_bounds(today.year - 1, 12)
        return _month_bounds(today.year, today.month - 1)

    return None, None


def _extract_merchant_hint(question: str) -> str | None:
    lowered = question.lower().strip()
    patterns = [
        r"how has\s+(.+?)\s+changed",
        r"compare\s+(.+?)\s+(?:from|between)",
        r"what about\s+(.+?)\s+(?:this month|last month)",
    ]
    for pattern in patterns:
        match = re.search(pattern, lowered)
        if match:
            candidate = match.group(1).strip(" ?.,")
            if candidate:
                return candidate

    stop_words = {
        "how",
        "has",
        "changed",
        "compared",
        "compare",
        "last",
        "this",
        "month",
        "to",
        "from",
        "the",
        "my",
    }
    tokens = [t for t in re.findall(r"[a-z0-9&._-]+", lowered) if t not in stop_words]
    if tokens:
        return tokens[0]
    return None


def _pct_change(from_value: float, to_value: float) -> str:
    if abs(from_value) < 1e-9:
        return "n/a"
    pct = ((to_value - from_value) / from_value) * 100
    return f"{pct:.2f}%"


async def _resolve_two_months(
    db: AsyncSession,
    question: str,
    date_from: date | None,
    date_to: date | None,
) -> tuple[tuple[date, date], tuple[date, date]] | None:
    explicit = _extract_month_year_pairs(question)
    if len(explicit) >= 2:
        first = _month_bounds(explicit[0][0], explicit[0][1])
        second = _month_bounds(explicit[1][0], explicit[1][1])
        return first, second

    month_expr = func.date_trunc("month", Transaction.date).label("month_start")
    stmt = select(month_expr).distinct().order_by(month_expr.desc()).limit(2)
    if date_from is not None:
        stmt = stmt.where(Transaction.date >= date_from)
    if date_to is not None:
        stmt = stmt.where(Transaction.date <= date_to)

    months = [row.month_start.date() for row in (await db.execute(stmt)).all()]
    if len(months) < 2:
        return None

    newer = _month_bounds(months[0].year, months[0].month)
    older = _month_bounds(months[1].year, months[1].month)
    return older, newer


async def _sql_context(
    db: AsyncSession,
    question: str,
    date_from: date | None,
    date_to: date | None,
) -> list[ChatSource]:
    lowered = question.lower()

    has_compare_intent = ("compare" in lowered) or ("compared" in lowered)
    if has_compare_intent and "month" in lowered and (
        "merchant" in lowered or "how has" in lowered or "changed" in lowered
    ):
        merchant_hint = _extract_merchant_hint(question)
        if merchant_hint:
            month_ranges = await _resolve_two_months(db, question, date_from, date_to)
            if month_ranges is None:
                return [ChatSource(source_type="sql", title="Merchant month comparison", content="Not enough monthly data to compare.")]

            (first_start, first_end), (second_start, second_end) = month_ranges
            month_expr = func.to_char(func.date_trunc("month", Transaction.date), "YYYY-MM")
            stmt = (
                select(
                    month_expr.label("month"),
                    Merchant.normalized_name.label("merchant_name"),
                    func.coalesce(func.sum(Transaction.amount_gel), 0).label("spend"),
                    func.count(Transaction.id).label("tx_count"),
                )
                .join(Merchant, Merchant.id == Transaction.merchant_id)
                .where(
                    Transaction.direction == "expense",
                    Transaction.date >= first_start,
                    Transaction.date <= second_end,
                    Merchant.normalized_name.ilike(f"%{merchant_hint}%"),
                )
                .group_by(month_expr, Merchant.normalized_name)
                .order_by(func.sum(Transaction.amount_gel).desc())
            )
            rows = (await db.execute(stmt)).all()
            if not rows:
                return [
                    ChatSource(
                        source_type="sql",
                        title="Merchant month comparison",
                        content=f"No expense rows found for merchant hint '{merchant_hint}' in compared months.",
                    )
                ]

            first_label = first_start.strftime("%Y-%m")
            second_label = second_start.strftime("%Y-%m")
            best_name = rows[0].merchant_name or merchant_hint
            by_month = {row.month: float(row.spend) for row in rows}
            first_spend = by_month.get(first_label, 0.0)
            second_spend = by_month.get(second_label, 0.0)
            delta = second_spend - first_spend
            content = (
                f"- Merchant: {best_name}\n"
                f"- {first_label}: GEL {first_spend:.2f}\n"
                f"- {second_label}: GEL {second_spend:.2f}\n"
                f"- Delta: GEL {delta:.2f}\n"
                f"- Percent change: {_pct_change(first_spend, second_spend)}"
            )
            return [ChatSource(source_type="sql", title="Merchant month comparison", content=content)]

    if has_compare_intent and ("month" in lowered or len(_extract_month_year_pairs(question)) >= 2):
        month_ranges = await _resolve_two_months(db, question, date_from, date_to)
        if month_ranges is None:
            return [ChatSource(source_type="sql", title="Month comparison", content="Not enough monthly data to compare.")]

        (first_start, first_end), (second_start, second_end) = month_ranges
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
        stmt = (
            select(
                month_expr.label("month"),
                spent_expr.label("spent"),
                income_expr.label("income"),
                count_expr.label("count"),
            )
            .where(Transaction.date >= first_start, Transaction.date <= second_end)
            .group_by(month_expr)
            .order_by(month_expr.asc())
        )
        rows = (await db.execute(stmt)).all()
        by_month = {row.month: row for row in rows}
        first_label = first_start.strftime("%Y-%m")
        second_label = second_start.strftime("%Y-%m")
        first = by_month.get(first_label)
        second = by_month.get(second_label)

        if first is None and second is None:
            return [ChatSource(source_type="sql", title="Month comparison", content="No rows found for the compared months.")]

        first_spent = float(first.spent) if first else 0.0
        first_income = float(first.income) if first else 0.0
        first_net = first_income - first_spent
        second_spent = float(second.spent) if second else 0.0
        second_income = float(second.income) if second else 0.0
        second_net = second_income - second_spent

        content = (
            f"- {first_label}: spend GEL {first_spent:.2f}, income GEL {first_income:.2f}, net GEL {first_net:.2f}, tx {int(first.count) if first else 0}\n"
            f"- {second_label}: spend GEL {second_spent:.2f}, income GEL {second_income:.2f}, net GEL {second_net:.2f}, tx {int(second.count) if second else 0}\n"
            f"- Spend change ({first_label}->{second_label}): {_pct_change(first_spent, second_spent)}\n"
            f"- Income change ({first_label}->{second_label}): {_pct_change(first_income, second_income)}\n"
            f"- Net change ({first_label}->{second_label}): {_pct_change(first_net, second_net)}"
        )
        return [ChatSource(source_type="sql", title="Month comparison", content=content)]

    if ("category" in lowered or "categories" in lowered) and (
        "increase" in lowered or "increased" in lowered
    ):
        month_ranges = await _resolve_two_months(db, question, date_from, date_to)
        if month_ranges is None:
            return [ChatSource(source_type="sql", title="Category month-over-month", content="Not enough monthly data to compare categories.")]

        (first_start, first_end), (second_start, second_end) = month_ranges
        month_expr = func.to_char(func.date_trunc("month", Transaction.date), "YYYY-MM")
        category_expr = func.coalesce(Merchant.category, "Other")
        stmt = (
            select(
                month_expr.label("month"),
                category_expr.label("category"),
                func.coalesce(func.sum(Transaction.amount_gel), 0).label("spend"),
            )
            .outerjoin(Merchant, Merchant.id == Transaction.merchant_id)
            .where(
                Transaction.direction == "expense",
                Transaction.date >= first_start,
                Transaction.date <= second_end,
            )
            .group_by(month_expr, category_expr)
        )
        rows = (await db.execute(stmt)).all()
        first_label = first_start.strftime("%Y-%m")
        second_label = second_start.strftime("%Y-%m")

        by_category: dict[str, dict[str, float]] = {}
        for row in rows:
            bucket = by_category.setdefault(row.category, {first_label: 0.0, second_label: 0.0})
            bucket[row.month] = float(row.spend)

        deltas: list[tuple[str, float, float, float]] = []
        for category, spends in by_category.items():
            first_spend = spends.get(first_label, 0.0)
            second_spend = spends.get(second_label, 0.0)
            delta = second_spend - first_spend
            deltas.append((category, first_spend, second_spend, delta))

        deltas.sort(key=lambda item: item[3], reverse=True)
        if not deltas:
            return [ChatSource(source_type="sql", title="Category month-over-month", content="No category rows found for the compared months.")]

        content_lines = []
        for category, first_spend, second_spend, delta in deltas[:10]:
            pct_text = _pct_change(first_spend, second_spend)
            content_lines.append(
                f"- {category}: {first_label} GEL {first_spend:.2f} -> {second_label} GEL {second_spend:.2f} | delta GEL {delta:.2f} | pct {pct_text}"
            )

        return [ChatSource(source_type="sql", title="Category month-over-month", content="\n".join(content_lines))]

    if "top" in lowered and "merchant" in lowered:
        stmt = (
            select(
                Merchant.id.label("merchant_id"),
                Merchant.normalized_name.label("merchant_name"),
                func.coalesce(func.sum(Transaction.amount_gel), 0).label("spend"),
                func.count(Transaction.id).label("tx_count"),
            )
            .outerjoin(Merchant, Merchant.id == Transaction.merchant_id)
            .where(Transaction.direction == "expense")
            .group_by(Merchant.id, Merchant.normalized_name)
            .order_by(func.sum(Transaction.amount_gel).desc())
            .limit(10)
        )
        stmt = _apply_date_filter(stmt, date_from, date_to)
        rows = (await db.execute(stmt)).all()
        total_stmt = select(func.coalesce(func.sum(Transaction.amount_gel), 0)).where(
            Transaction.direction == "expense"
        )
        total_stmt = _apply_date_filter(total_stmt, date_from, date_to)
        total_spend = float((await db.execute(total_stmt)).scalar_one() or 0)
        content = "\n".join(
            (
                f"- {(row.merchant_name or 'unknown')}: GEL {float(row.spend):.2f} "
                f"({(float(row.spend) / total_spend * 100):.2f}% of total, {row.tx_count} tx)"
                if total_spend > 0
                else f"- {(row.merchant_name or 'unknown')}: GEL {float(row.spend):.2f} ({row.tx_count} tx)"
            )
            for row in rows
        ) or "No expense rows found for this period."
        if total_spend > 0:
            content = f"- Total spend: GEL {total_spend:.2f}\n{content}"
        return [ChatSource(source_type="sql", title="Top merchants", content=content)]

    if "category" in lowered:
        stmt = (
            select(
                func.coalesce(Merchant.category, "Other").label("category"),
                func.coalesce(func.sum(Transaction.amount_gel), 0).label("spend"),
                func.count(Transaction.id).label("tx_count"),
            )
            .outerjoin(Merchant, Merchant.id == Transaction.merchant_id)
            .where(Transaction.direction == "expense")
            .group_by(func.coalesce(Merchant.category, "Other"))
            .order_by(func.sum(Transaction.amount_gel).desc())
        )
        stmt = _apply_date_filter(stmt, date_from, date_to)
        rows = (await db.execute(stmt)).all()
        content = "\n".join(
            f"- {row.category}: GEL {float(row.spend):.2f} ({row.tx_count} tx)" for row in rows
        ) or "No expense rows found for this period."
        return [ChatSource(source_type="sql", title="Spending by category", content=content)]

    if "month" in lowered or "trend" in lowered:
        month_expr = func.to_char(func.date_trunc("month", Transaction.date), "YYYY-MM")
        stmt = (
            select(
                month_expr.label("month"),
                func.coalesce(func.sum(Transaction.amount_gel), 0).label("spend"),
            )
            .where(Transaction.direction == "expense")
            .group_by(month_expr)
            .order_by(month_expr.asc())
        )
        stmt = _apply_date_filter(stmt, date_from, date_to)
        rows = (await db.execute(stmt)).all()
        content = "\n".join(
            f"- {row.month}: GEL {float(row.spend):.2f}" for row in rows
        ) or "No monthly expense rows found for this period."
        return [ChatSource(source_type="sql", title="Monthly trend", content=content)]

    spent_expr = func.coalesce(
        func.sum(case((Transaction.direction == "expense", Transaction.amount_gel), else_=0)),
        0,
    )
    income_expr = func.coalesce(
        func.sum(case((Transaction.direction == "income", Transaction.amount_gel), else_=0)),
        0,
    )
    count_expr = func.count(Transaction.id)

    stmt = select(spent_expr.label("spent"), income_expr.label("income"), count_expr.label("count")).select_from(Transaction)
    stmt = _apply_date_filter(stmt, date_from, date_to)
    row = (await db.execute(stmt)).one()
    spent = float(row.spent or 0)
    income = float(row.income or 0)
    net = income - spent
    content = (
        f"- Total spend: GEL {spent:.2f}\n"
        f"- Total income: GEL {income:.2f}\n"
        f"- Net cash flow: GEL {net:.2f}\n"
        f"- Transactions: {int(row.count or 0)}"
    )
    return [ChatSource(source_type="sql", title="Summary", content=content)]


async def _semantic_context(
    db: AsyncSession,
    question: str,
    date_from: date | None,
    date_to: date | None,
    top_k: int,
) -> list[ChatSource]:
    if not _llm_available():
        return []

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    embedding_response = await client.embeddings.create(
        model="text-embedding-3-small", input=question
    )
    query_vector = embedding_response.data[0].embedding

    distance_expr = Transaction.embedding.cosine_distance(query_vector)
    stmt = (
        select(
            Transaction.date,
            Transaction.description_raw,
            Transaction.direction,
            Transaction.amount_gel,
            Transaction.currency_original,
            func.coalesce(Merchant.normalized_name, "unknown").label("merchant"),
            distance_expr.label("distance"),
        )
        .outerjoin(Merchant, Merchant.id == Transaction.merchant_id)
        .where(Transaction.embedding.is_not(None))
        .order_by(distance_expr.asc())
        .limit(top_k)
    )
    stmt = _apply_date_filter(stmt, date_from, date_to)
    rows = (await db.execute(stmt)).all()
    if not rows:
        return []

    lines = [
        (
            f"- {row.date} | {row.merchant} | {row.direction} | GEL {float(row.amount_gel):.2f} | "
            f"{row.description_raw[:180]}"
        )
        for row in rows
    ]
    return [ChatSource(source_type="semantic", title="Relevant transactions", content="\n".join(lines))]


def _fallback_answer(question: str, sources: list[ChatSource]) -> str:
    if not sources:
        return "I could not find relevant data to answer that question yet."
    intro = "I could not use LLM synthesis, so here is a direct data-backed summary."
    blocks = "\n\n".join(f"{src.title}:\n{src.content}" for src in sources)
    return f"{intro}\n\nQuestion: {question}\n\n{blocks}"


async def answer_chat(
    db: AsyncSession,
    question: str,
    date_from: date | None,
    date_to: date | None,
    top_k: int,
) -> ChatResponse:
    effective_date_from, effective_date_to = _infer_date_range_from_question(
        question, date_from, date_to
    )

    wants_sql = _question_wants_sql(question)
    wants_semantic = _question_wants_semantic(question)
    if wants_sql and _is_aggregate_question(question):
        wants_semantic = False
    if not wants_sql and not wants_semantic:
        wants_sql = True
        wants_semantic = True

    sources: list[ChatSource] = []
    if wants_sql:
        sources.extend(
            await _sql_context(db, question, effective_date_from, effective_date_to)
        )
    if wants_semantic:
        try:
            sources.extend(
                await _semantic_context(
                    db, question, effective_date_from, effective_date_to, top_k
                )
            )
        except Exception:
            pass

    if wants_sql and wants_semantic:
        mode = "mixed"
    elif wants_sql:
        mode = "sql"
    else:
        mode = "semantic"

    if not _llm_available():
        return ChatResponse(mode=mode, answer=_fallback_answer(question, sources), sources=sources)

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    context_payload = [
        {"source_type": s.source_type, "title": s.title, "content": s.content}
        for s in sources
    ]

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.1,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a finance assistant. Use only provided context. "
                        "If context is insufficient, say what is missing. "
                        "Keep answers concise and include numbers when available."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {"question": question, "context": context_payload}, ensure_ascii=False
                    ),
                },
            ],
        )
        answer = (response.choices[0].message.content or "").strip()
        if not answer:
            answer = _fallback_answer(question, sources)
    except Exception:
        answer = _fallback_answer(question, sources)

    return ChatResponse(mode=mode, answer=answer, sources=sources)
