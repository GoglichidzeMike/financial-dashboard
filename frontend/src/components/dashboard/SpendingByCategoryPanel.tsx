import { Card } from "../ui/Card";
import {
  CategoryMerchantBreakdownResponse,
  SpendingByCategoryItem,
} from "../../types/api";
import { formatGel, toPercent } from "../../lib/format";

type SpendingByCategoryPanelProps = {
  items: SpendingByCategoryItem[];
  loading: boolean;
  expandedCategory: string | null;
  onToggleCategory: (category: string) => void;
  breakdownByCategory: Record<
    string,
    {
      loading: boolean;
      error?: string;
      data?: CategoryMerchantBreakdownResponse;
    }
  >;
};

export function SpendingByCategoryPanel({
  items,
  loading,
  expandedCategory,
  onToggleCategory,
  breakdownByCategory,
}: SpendingByCategoryPanelProps) {
  const total = items.reduce((acc, item) => acc + item.amount_gel, 0);

  return (
    <Card title="Spending by Category" subtitle="Expense transactions only">
      {loading && <div className="h-24 animate-pulse rounded bg-slate-100" />}
      {!loading && items.length === 0 && (
        <p className="text-sm text-slate-500">No expense data for selected period.</p>
      )}
      {!loading && items.length > 0 && (
        <ul className="space-y-3">
          {items.map((item) => (
            <li key={item.category} className="space-y-2 rounded-lg border border-slate-100 p-2">
              <button
                type="button"
                className="flex w-full items-center justify-between text-sm"
                onClick={() => onToggleCategory(item.category)}
              >
                <span className="font-medium text-slate-700">{item.category}</span>
                <div className="flex items-center gap-3">
                  <span className="text-slate-600">{formatGel(item.amount_gel)}</span>
                  <span className="text-xs font-semibold text-cyan-700">
                    {expandedCategory === item.category ? "Hide" : "Breakdown"}
                  </span>
                </div>
              </button>
              <div className="h-2 rounded-full bg-slate-100">
                <div
                  className="h-2 rounded-full bg-accent"
                  style={{ width: `${toPercent(item.amount_gel, total)}%` }}
                />
              </div>
              {expandedCategory === item.category && (
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-2">
                  {breakdownByCategory[item.category]?.loading && (
                    <p className="text-xs text-slate-500">Loading merchant breakdown...</p>
                  )}
                  {breakdownByCategory[item.category]?.error && (
                    <p className="text-xs text-rose-600">
                      {breakdownByCategory[item.category]?.error}
                    </p>
                  )}
                  {!breakdownByCategory[item.category]?.loading &&
                    !breakdownByCategory[item.category]?.error &&
                    (breakdownByCategory[item.category]?.data?.items.length ?? 0) === 0 && (
                      <p className="text-xs text-slate-500">No merchant rows for this category.</p>
                    )}
                  {!breakdownByCategory[item.category]?.loading &&
                    !breakdownByCategory[item.category]?.error &&
                    (breakdownByCategory[item.category]?.data?.items.length ?? 0) > 0 && (
                      <div className="overflow-x-auto">
                        <table className="min-w-full text-xs">
                          <thead>
                            <tr className="text-left uppercase tracking-wide text-slate-500">
                              <th className="px-2 py-1.5">Merchant</th>
                              <th className="px-2 py-1.5 text-right">Tx</th>
                              <th className="px-2 py-1.5 text-right">Spend</th>
                            </tr>
                          </thead>
                          <tbody>
                            {breakdownByCategory[item.category]?.data?.items.map((merchant) => (
                              <tr key={`${item.category}-${merchant.merchant_id ?? merchant.merchant_name}`}>
                                <td className="border-t border-slate-200 px-2 py-1.5 text-slate-700">
                                  {merchant.merchant_name}
                                </td>
                                <td className="border-t border-slate-200 px-2 py-1.5 text-right text-slate-600">
                                  {merchant.transaction_count}
                                </td>
                                <td className="border-t border-slate-200 px-2 py-1.5 text-right font-semibold text-slate-800">
                                  {formatGel(merchant.amount_gel)}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
