from pydantic import BaseModel


class DashboardSummaryResponse(BaseModel):
    total_spent_gel: float
    total_income_gel: float
    net_cash_flow_gel: float
    expense_transaction_count: int


class SpendingByCategoryItem(BaseModel):
    category: str
    amount_gel: float
    transaction_count: int


class SpendingByCategoryResponse(BaseModel):
    items: list[SpendingByCategoryItem]


class MonthlyTrendItem(BaseModel):
    month: str
    amount_gel: float


class MonthlyTrendResponse(BaseModel):
    items: list[MonthlyTrendItem]


class TopMerchantItem(BaseModel):
    merchant_id: int | None
    merchant_name: str
    amount_gel: float
    transaction_count: int


class TopMerchantsResponse(BaseModel):
    items: list[TopMerchantItem]


class CurrencyBreakdownItem(BaseModel):
    currency: str
    amount_original: float
    transaction_count: int


class CurrencyBreakdownResponse(BaseModel):
    items: list[CurrencyBreakdownItem]
