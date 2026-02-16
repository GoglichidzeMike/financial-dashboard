import { Card } from "../ui/Card";
import { DashboardSummaryResponse } from "../../types/api";
import { formatGel, formatNumber } from "../../lib/format";

type SummaryCardsProps = {
  summary: DashboardSummaryResponse | null;
  loading: boolean;
};

export function SummaryCards({ summary, loading }: SummaryCardsProps) {
  const skeleton = "h-6 w-24 animate-pulse rounded bg-slate-200";

  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      <Card title="Total Spend">
        <p className="text-2xl font-bold text-slate-900">
          {loading ? <span className={skeleton} /> : formatGel(summary?.total_spent_gel ?? 0)}
        </p>
      </Card>
      <Card title="Total Income">
        <p className="text-2xl font-bold text-emerald-700">
          {loading ? <span className={skeleton} /> : formatGel(summary?.total_income_gel ?? 0)}
        </p>
      </Card>
      <Card title="Net Cash Flow">
        <p className="text-2xl font-bold text-slate-900">
          {loading ? <span className={skeleton} /> : formatGel(summary?.net_cash_flow_gel ?? 0)}
        </p>
      </Card>
      <Card title="Expense Transactions">
        <p className="text-2xl font-bold text-slate-900">
          {loading ? (
            <span className={skeleton} />
          ) : (
            formatNumber(summary?.expense_transaction_count ?? 0)
          )}
        </p>
      </Card>
    </div>
  );
}
