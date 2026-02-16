import { Card } from "../ui/Card";
import { MonthlyTrendItem } from "../../types/api";
import { formatGel, formatMonthLabel, toPercent } from "../../lib/format";

type MonthlyTrendPanelProps = {
  items: MonthlyTrendItem[];
  loading: boolean;
};

export function MonthlyTrendPanel({ items, loading }: MonthlyTrendPanelProps) {
  const max = items.reduce((acc, item) => Math.max(acc, item.amount_gel), 0);

  return (
    <Card title="Monthly Trend" subtitle="Expense by month (GEL)">
      {loading && <div className="h-24 animate-pulse rounded bg-slate-100" />}
      {!loading && items.length === 0 && (
        <p className="text-sm text-slate-500">No monthly data for selected period.</p>
      )}
      {!loading && items.length > 0 && (
        <ul className="space-y-2">
          {items.map((item) => (
            <li key={item.month} className="grid grid-cols-[88px_1fr_auto] items-center gap-3">
              <span className="text-xs font-medium text-slate-500">{formatMonthLabel(item.month)}</span>
              <div className="h-2 rounded-full bg-slate-100">
                <div
                  className="h-2 rounded-full bg-teal-600"
                  style={{ width: `${toPercent(item.amount_gel, max)}%` }}
                />
              </div>
              <span className="text-xs font-semibold text-slate-700">{formatGel(item.amount_gel)}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
