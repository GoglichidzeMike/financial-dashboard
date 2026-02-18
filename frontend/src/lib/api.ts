import {
  CategoryMerchantBreakdownResponse,
  ChatMessageListResponse,
  ChatThreadCreateRequest,
  ChatThreadListResponse,
  ChatThreadResponse,
  ChatThreadUpdateRequest,
  ChatRequest,
  ChatResponse,
  TransactionListResponse,
  TransactionQueryParams,
  UploadAcceptedResponse,
  UploadStatusResponse,
  CategoriesResponse,
  CurrencyBreakdownResponse,
  DashboardSummaryResponse,
  DateFilter,
  HealthResponse,
  LlmCheckResponse,
  MerchantsResponse,
  MonthlyTrendResponse,
  SpendingByCategoryResponse,
  TopMerchantsResponse,
} from "../types/api";

const apiBase = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

function buildQuery(params: Record<string, string | undefined>): string {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value) {
      query.set(key, value);
    }
  });
  const encoded = query.toString();
  return encoded ? `?${encoded}` : "";
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, init);
  if (!response.ok) {
    const maybeJson = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(maybeJson?.detail ?? `HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}

function filterQuery(filters: DateFilter): string {
  return buildQuery({ date_from: filters.dateFrom, date_to: filters.dateTo });
}

function filterParams(filters: DateFilter): Record<string, string | undefined> {
  return { date_from: filters.dateFrom, date_to: filters.dateTo };
}

export const api = {
  baseUrl: apiBase,
  getHealth: () => fetchJson<HealthResponse>("/health"),
  checkLlm: () => fetchJson<LlmCheckResponse>("/llm/check"),
  listCategories: () => fetchJson<CategoriesResponse>("/categories"),
  listMerchants: () => fetchJson<MerchantsResponse>("/merchants?limit=300&offset=0"),
  updateMerchantCategory: (merchantId: number, category: string) =>
    fetchJson(`/merchants/${merchantId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ category }),
    }),
  uploadStatement: async (file: File, generateEmbeddings = true) => {
    const formData = new FormData();
    formData.append("file", file);
    return fetchJson<UploadAcceptedResponse>(
      `/upload${buildQuery({ generate_embeddings: String(generateEmbeddings) })}`,
      { method: "POST", body: formData }
    );
  },
  getUploadStatus: (uploadId: number) =>
    fetchJson<UploadStatusResponse>(`/upload/${uploadId}`),
  dashboardSummary: (filters: DateFilter) =>
    fetchJson<DashboardSummaryResponse>(`/dashboard/summary${filterQuery(filters)}`),
  spendingByCategory: (filters: DateFilter) =>
    fetchJson<SpendingByCategoryResponse>(`/dashboard/spending-by-category${filterQuery(filters)}`),
  categoryMerchants: (
    category: string,
    filters: DateFilter,
    limit = 20
  ) =>
    fetchJson<CategoryMerchantBreakdownResponse>(
      `/dashboard/category-merchants${buildQuery({
        ...filterParams(filters),
        category,
        limit: String(limit),
      })}`
    ),
  monthlyTrend: (filters: DateFilter) =>
    fetchJson<MonthlyTrendResponse>(`/dashboard/monthly-trend${filterQuery(filters)}`),
  topMerchants: (filters: DateFilter, limit = 10) =>
    fetchJson<TopMerchantsResponse>(
      `/dashboard/top-merchants${buildQuery({
        ...filterParams(filters),
        limit: String(limit),
      })}`
    ),
  currencyBreakdown: (filters: DateFilter) =>
    fetchJson<CurrencyBreakdownResponse>(`/dashboard/currency-breakdown${filterQuery(filters)}`),
  listTransactions: (params: TransactionQueryParams) =>
    fetchJson<TransactionListResponse>(
      `/transactions${buildQuery(
        Object.fromEntries(
          Object.entries(params).map(([key, value]) => [
            key,
            value == null
              ? undefined
              : Array.isArray(value)
                ? value.join(",")
                : String(value),
          ])
        )
      )}`
    ),
  deleteTransaction: (transactionId: number) =>
    fetchJson<{ status: string }>(`/transactions/${transactionId}`, { method: "DELETE" }),
  listChatThreads: (status?: "active" | "archived") =>
    fetchJson<ChatThreadListResponse>(`/chat/threads${buildQuery({ status })}`),
  createChatThread: (payload: ChatThreadCreateRequest) =>
    fetchJson<ChatThreadResponse>("/chat/threads", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  updateChatThread: (threadId: string, payload: ChatThreadUpdateRequest) =>
    fetchJson<ChatThreadResponse>(`/chat/threads/${threadId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  deleteChatThread: (threadId: string) =>
    fetchJson<{ status: string }>(`/chat/threads/${threadId}`, { method: "DELETE" }),
  listChatMessages: (threadId: string, limit = 100, before?: string) =>
    fetchJson<ChatMessageListResponse>(
      `/chat/threads/${threadId}/messages${buildQuery({
        limit: String(limit),
        before,
      })}`
    ),
  chat: (payload: ChatRequest) =>
    fetchJson<ChatResponse>("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
};
