export type HealthResponse = {
  status: string;
};

export type UploadResponse = {
  upload_id: number;
  filename: string;
  status: string;
  rows_total: number;
  rows_skipped_non_transaction: number;
  rows_invalid: number;
  rows_duplicate: number;
  rows_inserted: number;
  llm_used_count: number;
  fallback_used_count: number;
};

export type Merchant = {
  id: number;
  raw_name: string;
  normalized_name: string;
  category: string;
  category_source: string;
  mcc_code: string | null;
  transaction_count: number;
  total_spent: string;
};

export type MerchantsResponse = {
  items: Merchant[];
};

export type CategoriesResponse = {
  items: string[];
};

export type LlmCheckResponse = {
  configured: boolean;
  ok: boolean;
  model: string;
  response?: string;
  error?: string | null;
};

export type DashboardSummaryResponse = {
  total_spent_gel: number;
  total_income_gel: number;
  net_cash_flow_gel: number;
  expense_transaction_count: number;
};

export type SpendingByCategoryItem = {
  category: string;
  amount_gel: number;
  transaction_count: number;
};

export type SpendingByCategoryResponse = {
  items: SpendingByCategoryItem[];
};

export type MonthlyTrendItem = {
  month: string;
  amount_gel: number;
};

export type MonthlyTrendResponse = {
  items: MonthlyTrendItem[];
};

export type TopMerchantItem = {
  merchant_id: number | null;
  merchant_name: string;
  amount_gel: number;
  transaction_count: number;
};

export type TopMerchantsResponse = {
  items: TopMerchantItem[];
};

export type CurrencyBreakdownItem = {
  currency: string;
  amount_original: number;
  transaction_count: number;
};

export type CurrencyBreakdownResponse = {
  items: CurrencyBreakdownItem[];
};

export type DateFilter = {
  dateFrom: string;
  dateTo: string;
};
