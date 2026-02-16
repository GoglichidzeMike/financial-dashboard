import { Card } from "../ui/Card";
import { CurrencyBreakdownItem } from "../../types/api";
import { formatNumber } from "../../lib/format";

type CurrencyBreakdownPanelProps = {
  items: CurrencyBreakdownItem[];
  loading: boolean;
};

export function CurrencyBreakdownPanel({ items, loading }: CurrencyBreakdownPanelProps) {
  return (
    <Card title="Currency Breakdown" subtitle="Original currency amounts (expenses)">
      {loading && <div className="h-16 animate-pulse rounded bg-slate-100" />}
      {!loading && items.length === 0 && (
        <p className="text-sm text-slate-500">No currency data for selected period.</p>
      )}
      {!loading && items.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {items.map((item) => (
            <span
              key={item.currency}
              className="rounded-full bg-slate-100 px-3 py-1.5 text-xs font-semibold text-slate-700"
            >
              {item.currency}: {formatNumber(item.amount_original)} ({item.transaction_count})
            </span>
          ))}
        </div>
      )}
    </Card>
  );
}
