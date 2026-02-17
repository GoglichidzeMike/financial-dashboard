import { FormEvent, useEffect, useState } from "react";

import { api } from "../lib/api";
import { formatGel } from "../lib/format";
import {
  CategoriesResponse,
  CategoryMerchantBreakdownResponse,
  CurrencyBreakdownResponse,
  DashboardSummaryResponse,
  DateFilter,
  MerchantsResponse,
  MonthlyTrendResponse,
  SpendingByCategoryResponse,
  UploadAcceptedResponse,
  UploadStatusResponse,
  TopMerchantsResponse,
} from "../types/api";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Input } from "../components/ui/Input";
import { Select } from "../components/ui/Select";
import { StatusPill } from "../components/shared/StatusPill";
import { SectionTitle } from "../components/shared/SectionTitle";
import { SummaryCards } from "../components/dashboard/SummaryCards";
import { SpendingByCategoryPanel } from "../components/dashboard/SpendingByCategoryPanel";
import { MonthlyTrendPanel } from "../components/dashboard/MonthlyTrendPanel";
import { TopMerchantsPanel } from "../components/dashboard/TopMerchantsPanel";
import { CurrencyBreakdownPanel } from "../components/dashboard/CurrencyBreakdownPanel";

const TOP_MERCHANTS_LIMIT_STORAGE_KEY = "dashboard_top_merchants_limit";
const DEFAULT_FILTERS: DateFilter = { dateFrom: "", dateTo: "" };

type DashboardPageProps = {
  onAppliedFiltersChange: (filters: DateFilter) => void;
};

type BreakdownState = {
  loading: boolean;
  error?: string;
  data?: CategoryMerchantBreakdownResponse;
};

export function DashboardPage({ onAppliedFiltersChange }: DashboardPageProps) {
  const [filters, setFilters] = useState<DateFilter>(DEFAULT_FILTERS);
  const [dashboardError, setDashboardError] = useState("");
  const [dashboardLoading, setDashboardLoading] = useState(false);
  const [summary, setSummary] = useState<DashboardSummaryResponse | null>(null);
  const [spendingByCategory, setSpendingByCategory] =
    useState<SpendingByCategoryResponse["items"]>([]);
  const [monthlyTrend, setMonthlyTrend] = useState<MonthlyTrendResponse["items"]>([]);
  const [topMerchants, setTopMerchants] = useState<TopMerchantsResponse["items"]>([]);
  const [currencyBreakdown, setCurrencyBreakdown] =
    useState<CurrencyBreakdownResponse["items"]>([]);
  const [topMerchantsLimit, setTopMerchantsLimit] = useState(20);

  const [expandedCategory, setExpandedCategory] = useState<string | null>(null);
  const [breakdownByCategory, setBreakdownByCategory] = useState<
    Record<string, BreakdownState>
  >({});

  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [uploadAccepted, setUploadAccepted] = useState<UploadAcceptedResponse | null>(null);
  const [uploadResult, setUploadResult] = useState<UploadStatusResponse | null>(null);
  const [generateEmbeddings, setGenerateEmbeddings] = useState(true);

  const [categories, setCategories] = useState<CategoriesResponse["items"]>([]);
  const [merchants, setMerchants] = useState<MerchantsResponse["items"]>([]);
  const [merchantsLoading, setMerchantsLoading] = useState(false);
  const [merchantsError, setMerchantsError] = useState("");
  const [savingMerchantId, setSavingMerchantId] = useState<number | null>(null);

  useEffect(() => {
    const raw = window.localStorage.getItem(TOP_MERCHANTS_LIMIT_STORAGE_KEY);
    if (!raw) {
      return;
    }
    const parsed = Number(raw);
    if (Number.isFinite(parsed) && parsed >= 1 && parsed <= 100) {
      setTopMerchantsLimit(Math.floor(parsed));
    }
  }, []);

  useEffect(() => {
    window.localStorage.setItem(TOP_MERCHANTS_LIMIT_STORAGE_KEY, String(topMerchantsLimit));
  }, [topMerchantsLimit]);

  useEffect(() => {
    api
      .listCategories()
      .then((res) => setCategories(res.items))
      .catch(() => setCategories([]));
  }, []);

  const loadDashboard = async (activeFilters: DateFilter, limit = topMerchantsLimit) => {
    setDashboardLoading(true);
    setDashboardError("");
    try {
      const [summaryRes, byCategoryRes, trendRes, topRes, currencyRes] = await Promise.all([
        api.dashboardSummary(activeFilters),
        api.spendingByCategory(activeFilters),
        api.monthlyTrend(activeFilters),
        api.topMerchants(activeFilters, limit),
        api.currencyBreakdown(activeFilters),
      ]);
      setSummary(summaryRes);
      setSpendingByCategory(byCategoryRes.items);
      setMonthlyTrend(trendRes.items);
      setTopMerchants(topRes.items);
      setCurrencyBreakdown(currencyRes.items);
      setBreakdownByCategory({});
      setExpandedCategory(null);
      onAppliedFiltersChange(activeFilters);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "unknown error";
      setDashboardError(message);
    } finally {
      setDashboardLoading(false);
    }
  };

  useEffect(() => {
    void loadDashboard(filters, topMerchantsLimit);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [topMerchantsLimit]);

  const loadMerchants = async () => {
    setMerchantsLoading(true);
    setMerchantsError("");
    try {
      const res = await api.listMerchants();
      setMerchants(res.items);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "unknown error";
      setMerchantsError(message);
    } finally {
      setMerchantsLoading(false);
    }
  };

  const onSubmitFilters = async (event: FormEvent) => {
    event.preventDefault();
    await loadDashboard(filters, topMerchantsLimit);
  };

  const onToggleCategory = async (category: string) => {
    if (expandedCategory === category) {
      setExpandedCategory(null);
      return;
    }
    setExpandedCategory(category);
    const cacheKey = `${category}|${filters.dateFrom}|${filters.dateTo}`;
    if (breakdownByCategory[cacheKey]?.data || breakdownByCategory[cacheKey]?.loading) {
      return;
    }
    setBreakdownByCategory((prev) => ({ ...prev, [cacheKey]: { loading: true } }));
    try {
      const data = await api.categoryMerchants(category, filters);
      setBreakdownByCategory((prev) => ({ ...prev, [cacheKey]: { loading: false, data } }));
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "unknown error";
      setBreakdownByCategory((prev) => ({
        ...prev,
        [cacheKey]: { loading: false, error: `Failed to load breakdown: ${message}` },
      }));
    }
  };

  const activeBreakdown = expandedCategory
    ? breakdownByCategory[`${expandedCategory}|${filters.dateFrom}|${filters.dateTo}`]
    : undefined;

  const onUpload = async (event: FormEvent) => {
    event.preventDefault();
    if (!uploadFile) {
      setUploadError("Please select an .xlsx file first.");
      return;
    }

    setUploading(true);
    setUploadError("");
    setUploadResult(null);

    try {
      const accepted = await api.uploadStatement(uploadFile, generateEmbeddings);
      setUploadAccepted(accepted);

      const startedAt = Date.now();
      while (Date.now() - startedAt < 15 * 60 * 1000) {
        const status = await api.getUploadStatus(accepted.upload_id);
        setUploadResult(status);
        if (status.status === "done" || status.status === "error") {
          break;
        }
        await new Promise((resolve) => setTimeout(resolve, 2000));
      }

      await Promise.all([loadDashboard(filters, topMerchantsLimit), loadMerchants()]);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "unknown error";
      setUploadError(message);
    } finally {
      setUploading(false);
    }
  };

  const onChangeMerchantCategory = async (merchantId: number, category: string) => {
    setSavingMerchantId(merchantId);
    setMerchantsError("");
    try {
      await api.updateMerchantCategory(merchantId, category);
      setMerchants((prev) =>
        prev.map((merchant) =>
          merchant.id === merchantId
            ? { ...merchant, category, category_source: "user" }
            : merchant
        )
      );
      await loadDashboard(filters, topMerchantsLimit);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "unknown error";
      setMerchantsError(message);
    } finally {
      setSavingMerchantId(null);
    }
  };

  return (
    <main className="space-y-6">
      <section>
        <SectionTitle title="Dashboard" subtitle="Spending analytics and trends in GEL" />

        <Card className="mb-4">
          <form className="flex flex-wrap items-end gap-3" onSubmit={onSubmitFilters}>
            <label className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
              Date From
              <Input
                type="date"
                value={filters.dateFrom}
                onChange={(e) => setFilters((prev) => ({ ...prev, dateFrom: e.target.value }))}
              />
            </label>
            <label className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
              Date To
              <Input
                type="date"
                value={filters.dateTo}
                onChange={(e) => setFilters((prev) => ({ ...prev, dateTo: e.target.value }))}
              />
            </label>
            <div className="flex gap-2">
              <Button type="submit" disabled={dashboardLoading}>
                {dashboardLoading ? "Refreshing..." : "Apply Filters"}
              </Button>
              <Button
                type="button"
                variant="ghost"
                onClick={() => {
                  setFilters(DEFAULT_FILTERS);
                  void loadDashboard(DEFAULT_FILTERS, topMerchantsLimit);
                }}
              >
                Reset
              </Button>
            </div>
          </form>
          {dashboardError && (
            <p className="mt-3 text-sm font-medium text-rose-600">Dashboard error: {dashboardError}</p>
          )}
        </Card>

        <SummaryCards summary={summary} loading={dashboardLoading} />

        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          <SpendingByCategoryPanel
            items={spendingByCategory}
            loading={dashboardLoading}
            expandedCategory={expandedCategory}
            onToggleCategory={onToggleCategory}
            breakdownByCategory={
              expandedCategory
                ? {
                    [expandedCategory]: activeBreakdown ?? { loading: false },
                  }
                : {}
            }
          />
          <TopMerchantsPanel
            items={topMerchants}
            loading={dashboardLoading}
            limit={topMerchantsLimit}
            onLimitChange={setTopMerchantsLimit}
          />
          <MonthlyTrendPanel items={monthlyTrend} loading={dashboardLoading} />
          <CurrencyBreakdownPanel items={currencyBreakdown} loading={dashboardLoading} />
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <Card title="Upload Statement" subtitle="Import .xlsx bank exports">
          <form className="flex flex-wrap items-center gap-3" onSubmit={onUpload}>
            <Input
              type="file"
              accept=".xlsx"
              className="h-auto"
              onChange={(e) => {
                setUploadFile(e.target.files?.[0] ?? null);
                setUploadError("");
                setUploadAccepted(null);
                setUploadResult(null);
              }}
            />
            <label className="inline-flex items-center gap-2 text-xs text-slate-600">
              <input
                type="checkbox"
                checked={generateEmbeddings}
                onChange={(e) => setGenerateEmbeddings(e.target.checked)}
              />
              Generate embeddings
            </label>
            <Button type="submit" disabled={!uploadFile || uploading}>
              {uploading ? "Uploading..." : "Upload"}
            </Button>
          </form>
          {uploadError && <p className="mt-3 text-sm text-rose-600">Upload error: {uploadError}</p>}
          {uploadAccepted && (
            <p className="mt-3 text-xs text-slate-500">
              Upload job #{uploadAccepted.upload_id} is {uploadAccepted.status}...
            </p>
          )}
          {uploadResult && (
            <div className="mt-4 space-y-3 text-xs text-slate-600">
              <div>
                <div className="mb-1 flex items-center justify-between">
                  <span>
                    Progress: {uploadResult.progress_percent}% ({uploadResult.processing_phase})
                  </span>
                  <span>
                    {uploadResult.rows_processed}/
                    {Math.max(uploadResult.rows_total, uploadResult.rows_processed)}
                  </span>
                </div>
                <div className="h-2 w-full rounded-full bg-slate-200">
                  <div
                    className="h-2 rounded-full bg-accent transition-all"
                    style={{ width: `${uploadResult.progress_percent}%` }}
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                <span>Status: {uploadResult.status}</span>
                <span>Inserted: {uploadResult.rows_inserted}</span>
                <span>Duplicates: {uploadResult.rows_duplicate}</span>
                <span>Invalid: {uploadResult.rows_invalid}</span>
                <span>LLM used: {uploadResult.llm_used_count}</span>
                <span>Fallback used: {uploadResult.fallback_used_count}</span>
                <span>Embeddings: {uploadResult.embeddings_generated}</span>
                {uploadResult.error_message && (
                  <span className="col-span-2 text-rose-600">Error: {uploadResult.error_message}</span>
                )}
              </div>
            </div>
          )}
        </Card>

        <Card
          title="Merchants"
          subtitle="Review and override categories. Changes affect dashboard buckets immediately."
        >
          <div className="mb-3 flex justify-between">
            <Button variant="secondary" onClick={loadMerchants} disabled={merchantsLoading}>
              {merchantsLoading ? "Loading..." : "Load Merchants"}
            </Button>
            <span className="text-xs text-slate-500">Count: {merchants.length}</span>
          </div>
          {merchantsError && (
            <p className="mb-3 text-sm font-medium text-rose-600">Merchants error: {merchantsError}</p>
          )}
          {merchants.length > 0 && (
            <div className="max-h-[360px] overflow-auto rounded-lg border border-slate-100">
              <table className="min-w-full text-sm">
                <thead className="sticky top-0 bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-3 py-2">Merchant</th>
                    <th className="px-3 py-2">Category</th>
                    <th className="px-3 py-2 text-right">Tx</th>
                    <th className="px-3 py-2 text-right">Spent</th>
                  </tr>
                </thead>
                <tbody>
                  {merchants.map((merchant) => (
                    <tr key={merchant.id} className="odd:bg-white even:bg-slate-50/40">
                      <td className="px-3 py-2 text-slate-700">{merchant.normalized_name}</td>
                      <td className="px-3 py-2">
                        <div className="flex items-center gap-2">
                          <Select
                            value={merchant.category}
                            disabled={savingMerchantId === merchant.id || categories.length === 0}
                            onChange={(e) =>
                              void onChangeMerchantCategory(merchant.id, e.target.value)
                            }
                          >
                            {categories.map((category) => (
                              <option key={category} value={category}>
                                {category}
                              </option>
                            ))}
                          </Select>
                          <StatusPill
                            tone={merchant.category_source === "llm" ? "ok" : "neutral"}
                            label={merchant.category_source}
                          />
                        </div>
                      </td>
                      <td className="px-3 py-2 text-right text-slate-600">
                        {merchant.transaction_count}
                      </td>
                      <td className="px-3 py-2 text-right font-semibold text-slate-700">
                        {formatGel(Number(merchant.total_spent))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </section>
    </main>
  );
}
