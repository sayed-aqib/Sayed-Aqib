import { useQuery } from "@tanstack/react-query";
import { getUnitEconomicsSummary, type ChannelSummary, type SkuSummary } from "../lib/api";
import { formatINR, formatNumber, formatPct } from "../lib/format";
import { Card } from "../components/Card";
import { InfoTip } from "../components/InfoTip";
import { LowConfidenceBadge } from "../components/LowConfidenceBadge";

const CHANNEL_LABEL: Record<string, string> = { shopify: "Shopify", amazon: "Amazon" };

const COST_LINES: { key: keyof SkuSummary; label: string; definition: string }[] = [
  { key: "cogs", label: "Cost of goods", definition: "What we paid to make what sold — ingredients and production." },
  { key: "packaging", label: "Packaging", definition: "The jar, the label, the box — per unit sold." },
  { key: "shipping", label: "Shipping", definition: "What we pay the courier. On Shopify the customer is charged nothing for it, so this is a straight cost to us." },
  { key: "fees", label: "Platform fees", definition: "Amazon's referral and FBA cut, or the payment gateway's cut on Shopify." },
  { key: "returns_provision", label: "Returns provision", definition: "A set-aside for orders that come back, based on our return rate." },
  { key: "allocated_ad_spend", label: "Ad spend (allocated)", definition: "Total ad spend for this channel in the period, split across orders by units sold." },
];

function sumByChannel(skus: SkuSummary[], channel: string) {
  const rows = skus.filter((s) => s.channel === channel);
  const sum = (key: keyof SkuSummary) => rows.reduce((acc, r) => acc + (r[key] as number), 0);
  return {
    cogs: sum("cogs"),
    packaging: sum("packaging"),
    shipping: sum("shipping"),
    fees: sum("fees"),
    returns_provision: sum("returns_provision"),
    allocated_ad_spend: sum("allocated_ad_spend"),
  };
}

function ChannelCard({ summary, skus }: { summary: ChannelSummary; skus: SkuSummary[] }) {
  const breakdown = sumByChannel(skus, summary.channel);
  const positive = summary.contribution_margin >= 0;

  return (
    <Card>
      <div className="flex items-start justify-between">
        <h3 className="font-semibold text-ink">{CHANNEL_LABEL[summary.channel]}</h3>
        {summary.low_confidence && <LowConfidenceBadge sampleSize={summary.sample_size} />}
      </div>

      <div className="mt-3 flex items-baseline gap-2">
        <span className={`tabular-nums text-2xl font-semibold ${positive ? "text-positive" : "text-negative"}`}>
          {formatINR(summary.contribution_margin)}
        </span>
        <span className="tabular-nums text-sm text-ink-muted">{formatPct(summary.contribution_margin_pct, 1)} margin</span>
        <InfoTip>
          Contribution margin: what's left from each order after we pay for the product, the jar, shipping, platform
          fees, returns, and ads.
        </InfoTip>
      </div>

      <p className="tabular-nums mt-1 text-xs text-ink-muted">
        on {formatINR(summary.net_revenue)} net revenue
      </p>

      <dl className="mt-4 space-y-1.5 border-t border-border pt-3">
        {COST_LINES.map(({ key, label, definition }) => (
          <div key={String(key)} className="flex items-center justify-between text-sm">
            <dt className="flex items-center gap-1 text-ink-muted">
              {label}
              <InfoTip>{definition}</InfoTip>
            </dt>
            <dd className="tabular-nums text-ink">
              {formatINR(breakdown[key as keyof typeof breakdown])}
              <span className="ml-1 text-xs text-ink-muted">
                ({formatPct(summary.net_revenue ? breakdown[key as keyof typeof breakdown] / summary.net_revenue : 0, 1)})
              </span>
            </dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}

function SkuTable({ skus }: { skus: SkuSummary[] }) {
  const sorted = [...skus].sort((a, b) => b.contribution_margin - a.contribution_margin);

  return (
    <Card className="overflow-x-auto p-0">
      <table className="w-full min-w-[720px] border-collapse text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-ink-muted">
            <th className="px-4 py-2 font-medium">SKU</th>
            <th className="px-4 py-2 font-medium">Channel</th>
            <th className="px-4 py-2 text-right font-medium">Units</th>
            <th className="px-4 py-2 text-right font-medium">Net revenue</th>
            <th className="px-4 py-2 text-right font-medium">Contribution margin</th>
            <th className="px-4 py-2 text-right font-medium">Margin %</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((s) => (
            <tr key={`${s.product_id}-${s.channel}`} className="border-b border-border last:border-0">
              <td className="px-4 py-2 text-ink">{s.name}</td>
              <td className="px-4 py-2 text-ink-muted">{CHANNEL_LABEL[s.channel]}</td>
              <td className="tabular-nums px-4 py-2 text-right text-ink">{formatNumber(s.units)}</td>
              <td className="tabular-nums px-4 py-2 text-right text-ink">{formatINR(s.net_revenue)}</td>
              <td
                className={`tabular-nums px-4 py-2 text-right ${s.contribution_margin >= 0 ? "text-positive" : "text-negative"}`}
              >
                {formatINR(s.contribution_margin)}
              </td>
              <td className="tabular-nums px-4 py-2 text-right text-ink-muted">
                {formatPct(s.contribution_margin_pct, 1)}
                {s.low_confidence && <span className="ml-1 text-caution">·low n</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

export function UnitEconomics() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["unit-economics-summary"],
    queryFn: () => getUnitEconomicsSummary(),
  });

  if (isLoading) {
    return <p className="text-sm text-ink-muted">Loading unit economics…</p>;
  }
  if (isError || !data) {
    return (
      <Card>
        <p className="text-sm text-negative">Couldn't load unit economics: {(error as Error)?.message}</p>
        <p className="mt-1 text-xs text-ink-muted">
          Is the backend running? <code>uvicorn backend.api.main:app --reload</code>
        </p>
      </Card>
    );
  }

  const shopify = data.channels.find((c) => c.channel === "shopify");
  const amazon = data.channels.find((c) => c.channel === "amazon");

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-ink">Unit Economics</h2>
        <p className="text-sm text-ink-muted">
          Where the money actually goes, {data.start} to {data.end}. Amazon and Shopify are shown side by side on
          purpose — different fees, different shipping, different margin.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {shopify && <ChannelCard summary={shopify} skus={data.skus} />}
        {amazon && <ChannelCard summary={amazon} skus={data.skus} />}
      </div>

      <SkuTable skus={data.skus} />
    </div>
  );
}
