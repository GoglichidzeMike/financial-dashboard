export type HealthResponse = {
  status: string;
};

export type UploadAcceptedResponse = {
  upload_id: number;
  filename: string;
  status: string;
};

export type UploadStatusResponse = {
  upload_id: number;
  filename: string;
  status: string;
  processing_phase: string;
  progress_percent: number;
  rows_total: number;
  rows_processed: number;
  rows_skipped_non_transaction: number;
  rows_invalid: number;
  rows_duplicate: number;
  rows_inserted: number;
  llm_used_count: number;
  fallback_used_count: number;
  embeddings_generated: number;
  error_message: string | null;
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

export type CategoryMerchantBreakdownItem = {
  merchant_id: number | null;
  merchant_name: string;
  amount_gel: number;
  transaction_count: number;
};

export type CategoryMerchantBreakdownResponse = {
  category: string;
  total_amount_gel: number;
  total_transactions: number;
  items: CategoryMerchantBreakdownItem[];
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

export type TransactionSortBy =
  | "date"
  | "amount_gel"
  | "amount_original"
  | "merchant"
  | "category"
  | "direction";

export type TransactionSortOrder = "asc" | "desc";

export type TransactionListItem = {
  id: number;
  date: string;
  posted_date: string | null;
  description_raw: string;
  direction: "expense" | "income" | "transfer";
  amount_original: string;
  currency_original: string;
  amount_gel: string;
  conversion_rate: string | null;
  card_last4: string | null;
  mcc_code: string | null;
  upload_id: number | null;
  merchant_name: string | null;
  category: string | null;
};

export type TransactionListMeta = {
  total: number;
  limit: number;
  offset: number;
  has_next: boolean;
};

export type TransactionListResponse = {
  items: TransactionListItem[];
  meta: TransactionListMeta;
};

export type TransactionQueryParams = {
  limit?: number;
  offset?: number;
  upload_id?: number;
  date_from?: string;
  date_to?: string;
  direction?: "expense" | "income" | "transfer";
  category?: string;
  categories?: string[];
  merchant?: string;
  currency_original?: string;
  amount_gel_min?: number;
  amount_gel_max?: number;
  sort_by?: TransactionSortBy;
  sort_order?: TransactionSortOrder;
};

export type ChatSource = {
  source_type: string;
  title: string;
  content: string;
  table_columns?: string[] | null;
  table_rows?: string[][] | null;
};

export type ChatRequest = {
  question: string;
  date_from?: string;
  date_to?: string;
  top_k?: number;
  history?: ChatHistoryTurn[];
};

export type ChatHistoryTurn = {
  question: string;
  answer: string;
};

export type ChatResponse = {
  mode: string;
  answer: string;
  sources: ChatSource[];
};
