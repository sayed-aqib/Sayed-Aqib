import { useQuery } from "@tanstack/react-query";
import { getRetentionSummary, type CohortRow } from "../lib/api";
import { formatNumber, formatPct } from "../lib/format";
import { Card } from "../components/Card";
import { InfoTip } from "../components/InfoTip";
import { LowConfidenceBadge } from "../components/LowConfidenceBadge";
import { EmptyState } from "../components/EmptyState";

function StatCard({
  label,
  value,
  sub,
  definition,
  lowConfidence,
  sampleSize,
}: {
  label: string;
  value: string;
  sub?: string;
  definition: string;
  lowConfidence: boolean;
  sampleSize: number;
}) {
  return (
    <Card>
      <div className="flex items-center gap-1 text-sm text-ink-muted">
        {label}
        <InfoTip>{definition}</InfoTip>
      </div>
      <p className="tabular-nums mt-1 text-3xl font-semibold text-ink">{value}</p>
      {sub && <p className="tabular-nums mt-1 text-xs text-ink-muted">{sub}</p>}
      {lowConfidence && (
        <div className="mt-2">
          <LowConfidenceBadge sampleSize={sampleSize} />
        </div>
      )}
    </Card>
  );
}

function CohortTable({ rows }: { rows: CohortRow[] }) {
  const months = Array.from(new Set(rows.map((r) => r.months_since_first))).sort((a, b) => a - b);
  const cohorts = Array.from(new Set(rows.map((r) => r.cohort_month))).sort();
  const cellValue = (cohort: string, month: number) =>
    rows.find((r) => r.cohort_month === cohort && r.months_since_first === month)?.order_count;

  return (
    <Card className="overflow-x-auto p-0">
      <table className="w-full min-w-[600px] border-collapse text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-ink-muted">
            <th className="px-4 py-2 font-medium">Cohort</th>
            {months.map((m) => (
              <th key={m} className="px-3 py-2 text-right font-medium">
                Month {m}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {cohorts.map((cohort) => (
            <tr key={cohort} className="border-b border-border last:border-0">
              <td className="px-4 py-2 text-ink">{cohort}</td>
              {months.map((m) => {
                const v = cellValue(cohort, m);
                return (
                  <td key={m} className="tabular-nums px-3 py-2 text-right text-ink-muted">
                    {v === undefined ? "—" : formatNumber(v)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

export function Retention() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["retention-summary"],
    queryFn: () => getRetentionSummary(),
  });

  if (isLoading) {
    return <p className="text-sm text-ink-muted">Loading retention…</p>;
  }
  if (isError || !data) {
    return (
      <Card>
        <p className="text-sm text-negative">Couldn't load retention: {(error as Error)?.message}</p>
      </Card>
    );
  }

  if (!data.has_data) {
    return (
      <div className="space-y-2">
        <h2 className="text-lg font-semibold text-ink">Retention</h2>
        <EmptyState title="No Shopify orders yet" instruction="Drop a Shopify orders export into data/raw/shopify_orders/." />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-ink">Retention</h2>
        <p className="text-sm text-ink-muted">
          Shopify only — Amazon doesn't give sellers customer identity, so repeat behavior can't be measured there.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <StatCard
          label="Reorder gap"
          value={data.reorder_gap.median_days !== null ? `${Math.round(data.reorder_gap.median_days)} days` : "—"}
          sub="median days between a customer's 1st and 2nd order"
          definition="The number that tells us whether a subscription makes sense — if most repeat customers reorder around the same gap, that's the cadence to offer."
          lowConfidence={data.reorder_gap.low_confidence}
          sampleSize={data.reorder_gap.sample_size}
        />
        <StatCard
          label="Repeat purchase rate"
          value={formatPct(data.overall.repeat_rate, 0)}
          sub={`${formatNumber(data.overall.repeat_customers)} of ${formatNumber(data.overall.sample_size)} customers ordered again`}
          definition="Share of all Shopify customers who have placed more than one order, ever."
          lowConfidence={data.overall.low_confidence}
          sampleSize={data.overall.sample_size}
        />
        <StatCard
          label="Chukku Kappi → mix cross-sell"
          value={formatPct(data.cross_sell_from_chukku.conversion_rate, 0)}
          sub={`${formatNumber(data.cross_sell_from_chukku.converted)} of ${formatNumber(data.cross_sell_from_chukku.cohort_size)} first-time Chukku buyers`}
          definition="Of customers whose very first order was Chukku Kappi, the share who later bought a ₹999 Supermix in a separate order."
          lowConfidence={data.cross_sell_from_chukku.low_confidence}
          sampleSize={data.cross_sell_from_chukku.cohort_size}
        />
      </div>

      <Card>
        <h3 className="font-semibold text-ink">Repeat rate by first SKU</h3>
        <p className="text-xs text-ink-muted">Does what someone buys first predict whether they come back?</p>
        <div className="mt-3 space-y-2">
          {data.by_first_sku.map((row) => (
            <div key={row.first_sku} className="flex items-center justify-between text-sm">
              <span className="flex items-center gap-1.5 text-ink">
                {row.name}
                {row.low_confidence && <LowConfidenceBadge sampleSize={row.sample_size} />}
              </span>
              <span className="tabular-nums text-ink-muted">
                {formatPct(row.repeat_rate, 0)} ({formatNumber(row.repeat_customers)} of {formatNumber(row.sample_size)})
              </span>
            </div>
          ))}
        </div>
      </Card>

      <div>
        <h3 className="mb-2 flex items-center gap-1 font-semibold text-ink">
          Monthly cohorts
          <InfoTip>Orders placed by each cohort of first-time customers, counted by months since their first order.</InfoTip>
        </h3>
        <CohortTable rows={data.cohorts} />
      </div>
    </div>
  );
}
