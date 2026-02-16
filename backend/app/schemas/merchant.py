from decimal import Decimal

from pydantic import BaseModel, Field


class MerchantListItem(BaseModel):
    id: int
    raw_name: str
    normalized_name: str
    category: str
    category_source: str
    mcc_code: str | None
    transaction_count: int
    total_spent: Decimal


class MerchantListResponse(BaseModel):
    items: list[MerchantListItem]


class MerchantUpdateRequest(BaseModel):
    category: str = Field(min_length=1)


class MerchantUpdateResponse(BaseModel):
    id: int
    category: str
    category_source: str
