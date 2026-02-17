import {
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
  monthlyTrend: (filters: DateFilter) =>
    fetchJson<MonthlyTrendResponse>(`/dashboard/monthly-trend${filterQuery(filters)}`),
  topMerchants: (filters: DateFilter) =>
    fetchJson<TopMerchantsResponse>(
      `/dashboard/top-merchants${buildQuery({ ...filterParams(filters), limit: "10" })}`
    ),
  currencyBreakdown: (filters: DateFilter) =>
    fetchJson<CurrencyBreakdownResponse>(`/dashboard/currency-breakdown${filterQuery(filters)}`),
};
