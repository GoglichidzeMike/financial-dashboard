import { Card } from "../ui/Card";
import { TopMerchantItem } from "../../types/api";
import { formatGel } from "../../lib/format";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";
import { FormEvent, useState } from "react";

type TopMerchantsPanelProps = {
  items: TopMerchantItem[];
  loading: boolean;
  limit: number;
  onLimitChange: (next: number) => void;
};

const PRESET_LIMITS = [5, 10, 20, 50];

export function TopMerchantsPanel({
  items,
  loading,
  limit,
  onLimitChange,
}: TopMerchantsPanelProps) {
  const [customLimit, setCustomLimit] = useState(String(limit));

  const onSubmitCustom = (event: FormEvent) => {
    event.preventDefault();
    const parsed = Number(customLimit);
    if (!Number.isFinite(parsed)) {
      return;
    }
    const clamped = Math.max(1, Math.min(100, Math.floor(parsed)));
    onLimitChange(clamped);
    setCustomLimit(String(clamped));
  };

  return (
    <Card title="Top Merchants" subtitle="Sorted by total spend">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        {PRESET_LIMITS.map((value) => (
          <button
            key={value}
            type="button"
            className={`rounded-md border px-2.5 py-1 text-xs font-semibold transition ${value === limit ? "border-cyan-300 bg-cyan-50 text-cyan-700" : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"}`}
            onClick={() => onLimitChange(value)}
          >
            Top {value}
          </button>
        ))}
        <form className="ml-auto flex items-center gap-2" onSubmit={onSubmitCustom}>
          <Input
            type="number"
            min={1}
            max={100}
            className="h-8 w-24"
            value={customLimit}
            onChange={(event) => setCustomLimit(event.target.value)}
          />
          <Button type="submit" className="h-8 px-3 text-xs">
            Apply
          </Button>
        </form>
      </div>
      {loading && <div className="h-24 animate-pulse rounded bg-slate-100" />}
      {!loading && items.length === 0 && (
        <p className="text-sm text-slate-500">No merchant spend data for selected period.</p>
      )}
      {!loading && items.length > 0 && (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-slate-500">
                <th className="px-2 py-2">Merchant</th>
                <th className="px-2 py-2 text-right">Tx</th>
                <th className="px-2 py-2 text-right">Spend</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={`${item.merchant_id ?? "unknown"}-${item.merchant_name}`}>
                  <td className="border-t border-slate-100 px-2 py-2 font-medium text-slate-700">
                    {item.merchant_name}
                  </td>
                  <td className="border-t border-slate-100 px-2 py-2 text-right text-slate-600">
                    {item.transaction_count}
                  </td>
                  <td className="border-t border-slate-100 px-2 py-2 text-right font-semibold text-slate-800">
                    {formatGel(item.amount_gel)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
