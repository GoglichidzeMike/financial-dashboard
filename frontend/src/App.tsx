import { FormEvent, useEffect, useMemo, useState } from "react";

import { api } from "./lib/api";
import { formatGel } from "./lib/format";
import {
  CategoriesResponse,
  CurrencyBreakdownResponse,
  DashboardSummaryResponse,
  DateFilter,
  LlmCheckResponse,
  MerchantsResponse,
  MonthlyTrendResponse,
  SpendingByCategoryResponse,
  TopMerchantsResponse,
  UploadResponse,
} from "./types/api";
import { Button } from "./components/ui/Button";
import { Card } from "./components/ui/Card";
import { Input } from "./components/ui/Input";
import { Select } from "./components/ui/Select";
import { StatusPill } from "./components/shared/StatusPill";
import { SectionTitle } from "./components/shared/SectionTitle";
import { SummaryCards } from "./components/dashboard/SummaryCards";
import { SpendingByCategoryPanel } from "./components/dashboard/SpendingByCategoryPanel";
import { MonthlyTrendPanel } from "./components/dashboard/MonthlyTrendPanel";
import { TopMerchantsPanel } from "./components/dashboard/TopMerchantsPanel";
import { CurrencyBreakdownPanel } from "./components/dashboard/CurrencyBreakdownPanel";

const DEFAULT_FILTERS: DateFilter = {
  dateFrom: "",
  dateTo: "",
};

function App() {
  const [health, setHealth] = useState("loading");
  const [llmCheck, setLlmCheck] = useState<LlmCheckResponse | null>(null);
  const [checkingLlm, setCheckingLlm] = useState(false);

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

  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [uploadResult, setUploadResult] = useState<UploadResponse | null>(null);

  const [categories, setCategories] = useState<CategoriesResponse["items"]>([]);
  const [merchants, setMerchants] = useState<MerchantsResponse["items"]>([]);
  const [merchantsLoading, setMerchantsLoading] = useState(false);
  const [merchantsError, setMerchantsError] = useState("");
  const [savingMerchantId, setSavingMerchantId] = useState<number | null>(null);

  useEffect(() => {
    api
      .getHealth()
      .then((res) => setHealth(res.status))
      .catch((err: unknown) => {
        const message = err instanceof Error ? err.message : "unknown error";
        setHealth(`error: ${message}`);
      });
  }, []);

  useEffect(() => {
    api
      .listCategories()
      .then((res) => setCategories(res.items))
      .catch(() => setCategories([]));
  }, []);

  const loadDashboard = async (activeFilters: DateFilter) => {
    setDashboardLoading(true);
    setDashboardError("");
    try {
      const [summaryRes, byCategoryRes, trendRes, topRes, currencyRes] =
        await Promise.all([
          api.dashboardSummary(activeFilters),
          api.spendingByCategory(activeFilters),
          api.monthlyTrend(activeFilters),
          api.topMerchants(activeFilters),
          api.currencyBreakdown(activeFilters),
        ]);

      setSummary(summaryRes);
      setSpendingByCategory(byCategoryRes.items);
      setMonthlyTrend(trendRes.items);
      setTopMerchants(topRes.items);
      setCurrencyBreakdown(currencyRes.items);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "unknown error";
      setDashboardError(message);
    } finally {
      setDashboardLoading(false);
    }
  };

  useEffect(() => {
    void loadDashboard(filters);
  }, []);

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
    await loadDashboard(filters);
  };

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
      const result = await api.uploadStatement(uploadFile);
      setUploadResult(result);
      await Promise.all([loadDashboard(filters), loadMerchants()]);
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
      await loadDashboard(filters);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "unknown error";
      setMerchantsError(message);
    } finally {
      setSavingMerchantId(null);
    }
  };

  const onCheckLlm = async () => {
    setCheckingLlm(true);
    setLlmCheck(null);
    try {
      const result = await api.checkLlm();
      setLlmCheck(result);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "unknown error";
      setLlmCheck({
        configured: false,
        ok: false,
        model: "gpt-4o-mini",
        error: message,
      });
    } finally {
      setCheckingLlm(false);
    }
  };

  const llmTone = useMemo(() => {
    if (!llmCheck) {
      return "neutral" as const;
    }
    return llmCheck.ok ? "ok" : "error";
  }, [llmCheck]);

  return (
    <main className="mx-auto max-w-7xl space-y-6 px-6 py-8">
      <Card className="border border-cyan-100 bg-gradient-to-r from-white to-cyan-50">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-slate-900">Finance Dashboard</h1>
            <p className="mt-2 text-sm text-slate-600">
              Health: <span className="font-semibold">{health}</span> | API: {api.baseUrl}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Button variant="secondary" onClick={onCheckLlm} disabled={checkingLlm}>
              {checkingLlm ? "Checking LLM..." : "Check LLM"}
            </Button>
            {llmCheck && (
              <StatusPill
                tone={llmTone}
                label={llmCheck.ok ? "LLM Ready" : "LLM Unavailable"}
              />
            )}
          </div>
        </div>
        {llmCheck && (
          <p className="mt-3 text-xs text-slate-500">
            Model: {llmCheck.model}
            {llmCheck.error ? ` | Error: ${llmCheck.error}` : ""}
            {llmCheck.response ? ` | Response: ${llmCheck.response}` : ""}
          </p>
        )}
      </Card>

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
                  void loadDashboard(DEFAULT_FILTERS);
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
          <SpendingByCategoryPanel items={spendingByCategory} loading={dashboardLoading} />
          <MonthlyTrendPanel items={monthlyTrend} loading={dashboardLoading} />
          <TopMerchantsPanel items={topMerchants} loading={dashboardLoading} />
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
                setUploadResult(null);
              }}
            />
            <Button type="submit" disabled={!uploadFile || uploading}>
              {uploading ? "Uploading..." : "Upload"}
            </Button>
          </form>
          {uploadError && <p className="mt-3 text-sm text-rose-600">Upload error: {uploadError}</p>}
          {uploadResult && (
            <div className="mt-4 grid grid-cols-2 gap-2 text-xs text-slate-600 sm:grid-cols-3">
              <span>Status: {uploadResult.status}</span>
              <span>Inserted: {uploadResult.rows_inserted}</span>
              <span>Duplicates: {uploadResult.rows_duplicate}</span>
              <span>Invalid: {uploadResult.rows_invalid}</span>
              <span>LLM used: {uploadResult.llm_used_count}</span>
              <span>Fallback used: {uploadResult.fallback_used_count}</span>
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
                      <td className="px-3 py-2 text-right text-slate-600">{merchant.transaction_count}</td>
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

export default App;
