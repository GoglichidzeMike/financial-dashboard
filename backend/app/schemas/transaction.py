from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class TransactionListItem(BaseModel):
    id: int
    date: date
    posted_date: date | None
    description_raw: str
    direction: str
    amount_original: Decimal
    currency_original: str
    amount_gel: Decimal
    conversion_rate: Decimal | None
    card_last4: str | None
    mcc_code: str | None
    upload_id: int | None
    merchant_name: str | None
    category: str | None


class TransactionListMeta(BaseModel):
    total: int
    limit: int
    offset: int
    has_next: bool


class TransactionListResponse(BaseModel):
    items: list[TransactionListItem]
    meta: TransactionListMeta
