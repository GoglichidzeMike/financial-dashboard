import { Card } from "../ui/Card";
import { TopMerchantItem } from "../../types/api";
import { formatGel } from "../../lib/format";

type TopMerchantsPanelProps = {
  items: TopMerchantItem[];
  loading: boolean;
};

export function TopMerchantsPanel({ items, loading }: TopMerchantsPanelProps) {
  return (
    <Card title="Top Merchants" subtitle="Sorted by total spend">
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
