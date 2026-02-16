from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.category import Category
from app.models.merchant import Merchant
from app.services.parser import ParsedTransaction

DEFAULT_CATEGORIES = [
    "Groceries",
    "Dining & Restaurants",
    "Food Delivery",
    "Transport & Taxi",
    "Utilities",
    "Subscriptions",
    "Shopping & Clothing",
    "Pharmacy & Health",
    "Travel & Flights",
    "Home & Furniture",
    "Parking",
    "Fuel",
    "Online Shopping",
    "Income & Transfers",
    "Other",
]

MCC_CATEGORY_MAP: dict[str, str] = {
    "5411": "Groceries",
    "5812": "Dining & Restaurants",
    "5814": "Dining & Restaurants",
    "4215": "Food Delivery",
    "4121": "Transport & Taxi",
    "4112": "Transport & Taxi",
    "4899": "Subscriptions",
    "5818": "Subscriptions",
    "5734": "Subscriptions",
    "5912": "Pharmacy & Health",
    "5691": "Shopping & Clothing",
    "5712": "Home & Furniture",
    "5719": "Home & Furniture",
    "7523": "Parking",
    "5541": "Fuel",
    "5310": "Online Shopping",
    "5999": "Online Shopping",
}

KEYWORD_CATEGORY_MAP: list[tuple[str, str]] = [
    ("wolt", "Food Delivery"),
    ("bolttaxi", "Transport & Taxi"),
    ("bolt", "Transport & Taxi"),
    ("taxi", "Transport & Taxi"),
    ("nikora", "Groceries"),
    ("spar", "Groceries"),
    ("agrohub", "Groceries"),
    ("pharma", "Pharmacy & Health"),
    ("gpc", "Pharmacy & Health"),
    ("apple", "Subscriptions"),
    ("megogo", "Subscriptions"),
    ("t3 chat", "Subscriptions"),
    ("taobao", "Online Shopping"),
    ("zara", "Shopping & Clothing"),
    ("magti", "Utilities"),
    ("telmico", "Utilities"),
    ("gwp", "Utilities"),
    ("water", "Utilities"),
    ("power", "Utilities"),
]


@dataclass(slots=True)
class MerchantCandidate:
    raw_name: str
    normalized_name: str
    description_raw: str
    mcc_code: str | None
    direction: str


@dataclass(slots=True)
class MerchantEnrichment:
    normalized_name: str
    category: str
    source: str


@dataclass(slots=True)
class MerchantResolutionResult:
    merchant_ids: list[int | None]
    llm_used_count: int
    fallback_used_count: int


_MERCHANT_RE = re.compile(r"Merchant\s*:\s*(?P<merchant>.*?)(?:;|$)", re.IGNORECASE)
_PAYMENT_SERVICE_RE = re.compile(
    r"payment service,\s*(?P<merchant>[^,;]+)", re.IGNORECASE
)
_SENDER_RE = re.compile(r"Sender\s*:\s*(?P<sender>[^;]+)", re.IGNORECASE)


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def _is_automatic_conversion(description_raw: str) -> bool:
    return "automatic conversion" in description_raw.lower()


def _extract_merchant_brand(raw_merchant: str) -> str:
    cleaned = _clean_text(raw_merchant)
    if "," in cleaned:
        cleaned = cleaned.split(",", 1)[0].strip()
    cleaned = re.sub(r"\s+-\s+.*$", "", cleaned)
    return cleaned or "internal transfer"


def normalize_merchant_name(value: str) -> str:
    cleaned = value.lower()
    cleaned = re.sub(r"[^a-z0-9& ]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or "unknown"


def extract_merchant_raw(description_raw: str, direction: str) -> str:
    if _is_automatic_conversion(description_raw):
        return "internal transfer"
    if direction == "transfer":
        return "internal transfer"

    merchant_match = _MERCHANT_RE.search(description_raw)
    if merchant_match:
        return _extract_merchant_brand(merchant_match.group("merchant"))

    payment_service_match = _PAYMENT_SERVICE_RE.search(description_raw)
    if payment_service_match:
        return _clean_text(payment_service_match.group("merchant"))

    if direction == "income":
        return "income"

    sender_match = _SENDER_RE.search(description_raw)
    if sender_match:
        return _clean_text(sender_match.group("sender"))

    leading = description_raw.split(";", 1)[0]
    return _clean_text(leading[:80])


def infer_category_fallback(
    normalized_name: str, mcc_code: str | None, direction: str, allowed_categories: set[str]
) -> str:
    if direction == "transfer" or direction == "income":
        category = "Income & Transfers"
        return category if category in allowed_categories else "Other"

    if mcc_code and mcc_code in MCC_CATEGORY_MAP:
        category = MCC_CATEGORY_MAP[mcc_code]
        return category if category in allowed_categories else "Other"

    for keyword, category in KEYWORD_CATEGORY_MAP:
        if keyword in normalized_name:
            return category if category in allowed_categories else "Other"

    return "Other"


def _normalize_llm_category(category: str, allowed_categories: set[str]) -> str:
    if category in allowed_categories:
        return category

    lowered_map = {name.lower(): name for name in allowed_categories}
    return lowered_map.get(category.lower(), "Other")


async def _load_allowed_categories(db: AsyncSession) -> set[str]:
    rows = await db.execute(select(Category.name))
    names = set(rows.scalars().all())
    return names or set(DEFAULT_CATEGORIES)


def _llm_available() -> bool:
    key = settings.OPENAI_API_KEY.strip()
    return bool(key and key != "sk-your-key-here")


def _extract_json_array(text: str) -> list[dict[str, Any]]:
    cleaned = text.strip()
    if "```" in cleaned:
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    parsed = json.loads(cleaned)
    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)]
    if isinstance(parsed, dict):
        items = parsed.get("items")
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
    raise ValueError("LLM did not return a JSON array")


async def check_llm_connection() -> dict[str, Any]:
    if not _llm_available():
        return {
            "configured": False,
            "ok": False,
            "model": "gpt-4o-mini",
            "error": "OPENAI_API_KEY is missing or placeholder",
        }

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            messages=[
                {"role": "system", "content": "Reply with exactly: OK"},
                {"role": "user", "content": "Ping"},
            ],
            max_tokens=5,
        )
        content = (response.choices[0].message.content or "").strip()
        return {
            "configured": True,
            "ok": content.upper().startswith("OK"),
            "model": "gpt-4o-mini",
            "response": content,
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "configured": True,
            "ok": False,
            "model": "gpt-4o-mini",
            "error": str(exc),
        }


async def _batch_llm_enrich(
    candidates: list[MerchantCandidate], allowed_categories: set[str]
) -> dict[str, MerchantEnrichment]:
    if not candidates or not _llm_available():
        return {}

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    outputs: dict[str, MerchantEnrichment] = {}

    for start in range(0, len(candidates), 20):
        batch = candidates[start : start + 20]
        payload = [
            {
                "index": i,
                "description_raw": item.description_raw,
                "mcc_code": item.mcc_code,
                "heuristic_normalized_name": item.normalized_name,
                "direction": item.direction,
            }
            for i, item in enumerate(batch)
        ]

        prompt = (
            "You are a strict financial merchant normalizer and categorizer. "
            "Return ONLY JSON array. For each input item return object with keys: "
            "index (int), normalized_name (lowercase short merchant name), category (one of allowed categories)."
            f" Allowed categories: {sorted(allowed_categories)}."
        )

        try:
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": json.dumps(payload)},
                ],
            )

            content = response.choices[0].message.content or "[]"
            items = _extract_json_array(content)

            for raw_item in items:
                idx = raw_item.get("index")
                if not isinstance(idx, int) or idx < 0 or idx >= len(batch):
                    continue
                normalized = normalize_merchant_name(
                    str(raw_item.get("normalized_name") or batch[idx].normalized_name)
                )
                category = _normalize_llm_category(
                    str(raw_item.get("category") or "Other"), allowed_categories
                )
                outputs[batch[idx].normalized_name] = MerchantEnrichment(
                    normalized_name=normalized,
                    category=category,
                    source="llm",
                )
        except Exception:
            # Fall through to rule-based categories for this batch.
            continue

    return outputs


async def resolve_merchants_for_transactions(
    db: AsyncSession, transactions: list[ParsedTransaction]
) -> MerchantResolutionResult:
    if not transactions:
        return MerchantResolutionResult(
            merchant_ids=[],
            llm_used_count=0,
            fallback_used_count=0,
        )

    allowed_categories = await _load_allowed_categories(db)

    candidates: list[MerchantCandidate] = []
    for tx in transactions:
        raw_name = extract_merchant_raw(tx.description_raw, tx.direction)
        normalized_name = normalize_merchant_name(raw_name)
        candidates.append(
            MerchantCandidate(
                raw_name=raw_name,
                normalized_name=normalized_name,
                description_raw=tx.description_raw,
                mcc_code=tx.mcc_code,
                direction=tx.direction,
            )
        )

    normalized_names = sorted({c.normalized_name for c in candidates})
    existing_rows = await db.execute(
        select(Merchant).where(Merchant.normalized_name.in_(normalized_names))
    )
    existing_merchants = {
        merchant.normalized_name: merchant for merchant in existing_rows.scalars().all()
    }

    missing_candidates = [
        c for c in candidates if c.normalized_name not in existing_merchants
    ]

    representative_missing: dict[str, MerchantCandidate] = {}
    for candidate in missing_candidates:
        representative_missing.setdefault(candidate.normalized_name, candidate)

    llm_candidates = [
        candidate
        for candidate in representative_missing.values()
        if candidate.normalized_name != "internal transfer"
    ]
    llm_enrichment = await _batch_llm_enrich(llm_candidates, allowed_categories)

    insert_rows: list[dict[str, Any]] = []
    mapped_normalized: dict[str, str] = {}

    for base_normalized, candidate in representative_missing.items():
        enrichment = llm_enrichment.get(base_normalized)
        final_normalized = base_normalized
        if final_normalized == "internal transfer":
            category = "Income & Transfers" if "Income & Transfers" in allowed_categories else "Other"
        else:
            category = infer_category_fallback(
                normalized_name=base_normalized,
                mcc_code=candidate.mcc_code,
                direction=candidate.direction,
                allowed_categories=allowed_categories,
            )

        if enrichment:
            final_normalized = enrichment.normalized_name
            category = _normalize_llm_category(enrichment.category, allowed_categories)
            source = "llm"
        else:
            source = "rule"

        mapped_normalized[base_normalized] = final_normalized
        insert_rows.append(
            {
                "raw_name": candidate.raw_name,
                "normalized_name": final_normalized,
                "category": category,
                "category_source": source,
                "mcc_code": candidate.mcc_code,
            }
        )

    if insert_rows:
        stmt = insert(Merchant).values(insert_rows).on_conflict_do_nothing(
            index_elements=["normalized_name"]
        )
        await db.execute(stmt)
        await db.flush()

    needed_names = {c.normalized_name for c in candidates}
    needed_names.update(mapped_normalized.values())
    refreshed_rows = await db.execute(
        select(Merchant).where(Merchant.normalized_name.in_(sorted(needed_names)))
    )
    merchant_by_name = {
        merchant.normalized_name: merchant for merchant in refreshed_rows.scalars().all()
    }

    merchant_ids: list[int | None] = []
    llm_used_count = 0
    fallback_used_count = 0
    for candidate in candidates:
        normalized = candidate.normalized_name
        if normalized not in merchant_by_name and normalized in mapped_normalized:
            normalized = mapped_normalized[normalized]
        merchant = merchant_by_name.get(normalized)
        merchant_ids.append(merchant.id if merchant else None)
        if merchant:
            source = merchant.category_source
            if source == "llm":
                llm_used_count += 1
            elif source == "rule":
                fallback_used_count += 1

    return MerchantResolutionResult(
        merchant_ids=merchant_ids,
        llm_used_count=llm_used_count,
        fallback_used_count=fallback_used_count,
    )
