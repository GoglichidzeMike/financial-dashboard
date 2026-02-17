import { FormEvent, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { api } from "../lib/api";
import {
  CategoriesResponse,
  TransactionListResponse,
  TransactionQueryParams,
  TransactionSortBy,
  TransactionSortOrder,
} from "../types/api";
import { Card } from "../components/ui/Card";
import { Input } from "../components/ui/Input";
import { Button } from "../components/ui/Button";
import { Select } from "../components/ui/Select";
import { MultiSelectDropdown } from "../components/ui/MultiSelectDropdown";
import { SectionTitle } from "../components/shared/SectionTitle";

const PAGE_SIZE_OPTIONS = [25, 50, 100] as const;

type DraftFilters = {
  date_from: string;
  date_to: string;
  direction: string;
  categories: string[];
  merchant: string;
  currency_original: string;
  upload_id: string;
  amount_gel_min: string;
  amount_gel_max: string;
};

function parsePositiveInt(value: string | null, fallback: number): number {
  if (!value) {
    return fallback;
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < 0) {
    return fallback;
  }
  return Math.floor(parsed);
}

function parseQuery(searchParams: URLSearchParams): Required<
  Pick<TransactionQueryParams, "limit" | "offset" | "sort_by" | "sort_order">
> &
  Omit<TransactionQueryParams, "limit" | "offset" | "sort_by" | "sort_order"> {
  return {
    limit: parsePositiveInt(searchParams.get("limit"), 50) || 50,
    offset: parsePositiveInt(searchParams.get("offset"), 0),
    sort_by: (searchParams.get("sort_by") as TransactionSortBy) || "date",
    sort_order: (searchParams.get("sort_order") as TransactionSortOrder) || "desc",
    date_from: searchParams.get("date_from") || undefined,
    date_to: searchParams.get("date_to") || undefined,
    direction:
      (searchParams.get("direction") as "expense" | "income" | "transfer" | null) || undefined,
    category: searchParams.get("category") || undefined,
    categories: searchParams.get("categories")
      ? searchParams
          .get("categories")
          ?.split(",")
          .map((value) => value.trim())
          .filter(Boolean)
      : undefined,
    merchant: searchParams.get("merchant") || undefined,
    currency_original: searchParams.get("currency_original") || undefined,
    upload_id: searchParams.get("upload_id")
      ? Number(searchParams.get("upload_id"))
      : undefined,
    amount_gel_min: searchParams.get("amount_gel_min")
      ? Number(searchParams.get("amount_gel_min"))
      : undefined,
    amount_gel_max: searchParams.get("amount_gel_max")
      ? Number(searchParams.get("amount_gel_max"))
      : undefined,
  };
}

export function TransactionsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const query = useMemo(() => parseQuery(searchParams), [searchParams]);

  const [draft, setDraft] = useState<DraftFilters>({
    date_from: query.date_from || "",
    date_to: query.date_to || "",
    direction: query.direction || "",
    categories: query.categories || (query.category ? [query.category] : []),
    merchant: query.merchant || "",
    currency_original: query.currency_original || "",
    upload_id: query.upload_id ? String(query.upload_id) : "",
    amount_gel_min: query.amount_gel_min != null ? String(query.amount_gel_min) : "",
    amount_gel_max: query.amount_gel_max != null ? String(query.amount_gel_max) : "",
  });

  const [categories, setCategories] = useState<CategoriesResponse["items"]>([]);
  const [data, setData] = useState<TransactionListResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .listCategories()
      .then((res) => setCategories(res.items))
      .catch(() => setCategories([]));
  }, []);

  useEffect(() => {
    setDraft({
      date_from: query.date_from || "",
      date_to: query.date_to || "",
      direction: query.direction || "",
      categories: query.categories || (query.category ? [query.category] : []),
      merchant: query.merchant || "",
      currency_original: query.currency_original || "",
      upload_id: query.upload_id ? String(query.upload_id) : "",
      amount_gel_min: query.amount_gel_min != null ? String(query.amount_gel_min) : "",
      amount_gel_max: query.amount_gel_max != null ? String(query.amount_gel_max) : "",
    });
  }, [query]);

  useEffect(() => {
    setLoading(true);
    setError("");
    api
      .listTransactions(query)
      .then((response) => setData(response))
      .catch((err: unknown) => {
        const message = err instanceof Error ? err.message : "unknown error";
        setError(message);
      })
      .finally(() => setLoading(false));
  }, [query]);

  const setParams = (next: Record<string, string | undefined>) => {
    const params = new URLSearchParams(searchParams.toString());
    Object.entries(next).forEach(([key, value]) => {
      if (!value) {
        params.delete(key);
      } else {
        params.set(key, value);
      }
    });
    setSearchParams(params);
  };

  const onApplyFilters = (event: FormEvent) => {
    event.preventDefault();
    setParams({
      offset: "0",
      date_from: draft.date_from || undefined,
      date_to: draft.date_to || undefined,
      direction: draft.direction || undefined,
      category: undefined,
      categories: draft.categories.length > 0 ? draft.categories.join(",") : undefined,
      merchant: draft.merchant || undefined,
      currency_original: draft.currency_original || undefined,
      upload_id: draft.upload_id || undefined,
      amount_gel_min: draft.amount_gel_min || undefined,
      amount_gel_max: draft.amount_gel_max || undefined,
    });
  };

  const onResetFilters = () => {
    setDraft({
      date_from: "",
      date_to: "",
      direction: "",
      categories: [],
      merchant: "",
      currency_original: "",
      upload_id: "",
      amount_gel_min: "",
      amount_gel_max: "",
    });
    setParams({
      offset: "0",
      date_from: undefined,
      date_to: undefined,
      direction: undefined,
      category: undefined,
      categories: undefined,
      merchant: undefined,
      currency_original: undefined,
      upload_id: undefined,
      amount_gel_min: undefined,
      amount_gel_max: undefined,
    });
  };

  const onSort = (sortBy: TransactionSortBy) => {
    const nextOrder: TransactionSortOrder =
      query.sort_by === sortBy && query.sort_order === "desc" ? "asc" : "desc";
    setParams({
      sort_by: sortBy,
      sort_order: nextOrder,
      offset: "0",
    });
  };

  const pageSize = query.limit;
  const offset = query.offset;
  const currentPage = Math.floor(offset / pageSize) + 1;

  return (
    <main className="space-y-6">
      <section>
        <SectionTitle title="Transactions" subtitle="Filter, sort, and browse all imported transactions" />
        <Card>
          <form className="space-y-4" onSubmit={onApplyFilters}>
            <div className="grid grid-cols-5 gap-2">
              <div className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
                <label htmlFor="date-from">Date From</label>
                <Input
                  id="date-from"
                  type="date"
                  value={draft.date_from}
                  onChange={(e) => setDraft((prev) => ({ ...prev, date_from: e.target.value }))}
                />
              </div>
              <div className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
                <label htmlFor="date-to">Date To</label>
                <Input
                  id="date-to"
                  type="date"
                  value={draft.date_to}
                  onChange={(e) => setDraft((prev) => ({ ...prev, date_to: e.target.value }))}
                />
              </div>
              <div className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
                <label htmlFor="direction">Direction</label>
                <Select
                  id="direction"
                  value={draft.direction}
                  onChange={(e) => setDraft((prev) => ({ ...prev, direction: e.target.value }))}
                >
                  <option value="">All</option>
                  <option value="expense">expense</option>
                  <option value="income">income</option>
                  <option value="transfer">transfer</option>
                </Select>
              </div>
              <div className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
                <label>Category (multi-select)</label>
                <MultiSelectDropdown
                  options={categories}
                  selected={draft.categories}
                  onChange={(next) => setDraft((prev) => ({ ...prev, categories: next }))}
                  placeholder="All categories"
                />
              </div>
              <div className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
                <label htmlFor="merchant">Merchant</label>
                <Input
                  id="merchant"
                  type="text"
                  placeholder="Search merchant..."
                  value={draft.merchant}
                  onChange={(e) => setDraft((prev) => ({ ...prev, merchant: e.target.value }))}
                />
              </div>
              <div className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
                <label htmlFor="currency-original">Currency</label>
                <Select
                  id="currency-original"
                  value={draft.currency_original}
                  onChange={(e) =>
                    setDraft((prev) => ({ ...prev, currency_original: e.target.value }))
                  }
                >
                  <option value="">All</option>
                  <option value="GEL">GEL</option>
                  <option value="USD">USD</option>
                  <option value="EUR">EUR</option>
                  <option value="GBP">GBP</option>
                </Select>
              </div>
              <div className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
                <label htmlFor="upload-id">Upload ID</label>
                <Input
                  id="upload-id"
                  type="number"
                  value={draft.upload_id}
                  onChange={(e) => setDraft((prev) => ({ ...prev, upload_id: e.target.value }))}
                />
              </div>
              <div className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
                <label htmlFor="amount-gel-min">Min GEL</label>
                <Input
                  id="amount-gel-min"
                  type="number"
                  step="0.01"
                  value={draft.amount_gel_min}
                  onChange={(e) =>
                    setDraft((prev) => ({ ...prev, amount_gel_min: e.target.value }))
                  }
                />
              </div>
              <div className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
                <label htmlFor="amount-gel-max">Max GEL</label>
                <Input
                  id="amount-gel-max"
                  type="number"
                  step="0.01"
                  value={draft.amount_gel_max}
                  onChange={(e) =>
                    setDraft((prev) => ({ ...prev, amount_gel_max: e.target.value }))
                  }
                />
              </div>
            </div>
            <div className="col-span-full flex items-center gap-2">
              <Button type="submit">Apply Filters</Button>
              <Button type="button" variant="ghost" onClick={onResetFilters}>
                Reset
              </Button>
            </div>
          </form>
          {error && <p className="mt-3 text-sm text-rose-600">Transactions error: {error}</p>}
        </Card>
      </section>

      <section>
        <Card title="All Transactions" subtitle="Server-side pagination and sorting">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <div className="text-sm text-slate-600">
              Total rows: <span className="font-semibold">{data?.meta.total ?? 0}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Page Size
              </span>
              <Select
                value={String(pageSize)}
                onChange={(e) => setParams({ limit: e.target.value, offset: "0" })}
              >
                {PAGE_SIZE_OPTIONS.map((size) => (
                  <option key={size} value={size}>
                    {size}
                  </option>
                ))}
              </Select>
            </div>
          </div>

          {loading && <div className="h-24 animate-pulse rounded bg-slate-100" />}
          {!loading && (data?.items.length ?? 0) === 0 && (
            <p className="text-sm text-slate-500">No transactions matched your filters.</p>
          )}

          {!loading && (data?.items.length ?? 0) > 0 && (
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="sticky top-0 bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-2 py-2">
                      <button type="button" onClick={() => onSort("date")}>Date</button>
                    </th>
                    <th className="px-2 py-2">Posted</th>
                    <th className="px-2 py-2">
                      <button type="button" onClick={() => onSort("merchant")}>Merchant</button>
                    </th>
                    <th className="px-2 py-2">
                      <button type="button" onClick={() => onSort("category")}>Category</button>
                    </th>
                    <th className="px-2 py-2">Description</th>
                    <th className="px-2 py-2">
                      <button type="button" onClick={() => onSort("direction")}>Direction</button>
                    </th>
                    <th className="px-2 py-2 text-right">
                      <button type="button" onClick={() => onSort("amount_gel")}>Amount GEL</button>
                    </th>
                    <th className="px-2 py-2 text-right">
                      <button type="button" onClick={() => onSort("amount_original")}>Original</button>
                    </th>
                    <th className="px-2 py-2 text-right">Card</th>
                    <th className="px-2 py-2 text-right">MCC</th>
                  </tr>
                </thead>
                <tbody>
                  {data?.items.map((row) => (
                    <tr key={row.id} className="odd:bg-white even:bg-slate-50/40">
                      <td className="border-t border-slate-100 px-2 py-2">{row.date}</td>
                      <td className="border-t border-slate-100 px-2 py-2">
                        {row.posted_date ?? "-"}
                      </td>
                      <td className="border-t border-slate-100 px-2 py-2">{row.merchant_name ?? "-"}</td>
                      <td className="border-t border-slate-100 px-2 py-2">{row.category ?? "-"}</td>
                      <td
                        className="max-w-[280px] truncate border-t border-slate-100 px-2 py-2"
                        title={row.description_raw}
                      >
                        {row.description_raw}
                      </td>
                      <td className="border-t border-slate-100 px-2 py-2">{row.direction}</td>
                      <td className="border-t border-slate-100 px-2 py-2 text-right">
                        {row.amount_gel}
                      </td>
                      <td className="border-t border-slate-100 px-2 py-2 text-right">
                        {row.amount_original} {row.currency_original}
                      </td>
                      <td className="border-t border-slate-100 px-2 py-2 text-right">
                        {row.card_last4 ?? "-"}
                      </td>
                      <td className="border-t border-slate-100 px-2 py-2 text-right">
                        {row.mcc_code ?? "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="mt-4 flex items-center justify-between">
            <p className="text-xs text-slate-500">
              Page {currentPage}
              {data?.meta.total ? ` of ${Math.max(1, Math.ceil(data.meta.total / pageSize))}` : ""}
            </p>
            <div className="flex gap-2">
              <Button
                type="button"
                variant="secondary"
                disabled={offset <= 0}
                onClick={() => setParams({ offset: String(Math.max(0, offset - pageSize)) })}
              >
                Prev
              </Button>
              <Button
                type="button"
                variant="secondary"
                disabled={!data?.meta.has_next}
                onClick={() => setParams({ offset: String(offset + pageSize) })}
              >
                Next
              </Button>
            </div>
          </div>
        </Card>
      </section>
    </main>
  );
}
