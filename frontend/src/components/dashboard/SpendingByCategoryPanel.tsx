import { Card } from "../ui/Card";
import { SpendingByCategoryItem } from "../../types/api";
import { formatGel, toPercent } from "../../lib/format";

type SpendingByCategoryPanelProps = {
  items: SpendingByCategoryItem[];
  loading: boolean;
};

export function SpendingByCategoryPanel({ items, loading }: SpendingByCategoryPanelProps) {
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
            <li key={item.category} className="space-y-1">
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium text-slate-700">{item.category}</span>
                <span className="text-slate-600">{formatGel(item.amount_gel)}</span>
              </div>
              <div className="h-2 rounded-full bg-slate-100">
                <div
                  className="h-2 rounded-full bg-accent"
                  style={{ width: `${toPercent(item.amount_gel, total)}%` }}
                />
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
