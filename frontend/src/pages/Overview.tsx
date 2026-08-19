import { useQuery } from "@tanstack/react-query";
import { getUnitEconomicsSummary, getFunnelSummary, getRetentionSummary, getKeywordsSummary, getMetaAdsSummary } from "../lib/api";
import { formatPct } from "../lib/format";
import { Card } from "../components/Card";

function HeadlineCard({
  title,
  loading,
  value,
  sub,
  tone = "neutral",
}: {
  title: string;
  loading: boolean;
  value: string;
  sub: string;
  tone?: "positive" | "negative" | "neutral";
}) {
  const color = tone === "positive" ? "text-positive" : tone === "negative" ? "text-negative" : "text-ink";
  return (
    <Card>
      <p className="text-sm text-ink-muted">{title}</p>
      <p className={`tabular-nums mt-1 text-2xl font-semibold ${loading ? "text-ink-muted" : color}`}>
        {loading ? "…" : value}
      </p>
      <p className="mt-1 text-xs text-ink-muted">{sub}</p>
    </Card>
  );
}

export function Overview() {
  const ue = useQuery({ queryKey: ["unit-economics-summary"], queryFn: () => getUnitEconomicsSummary() });
  const funnel = useQuery({ queryKey: ["funnel-summary"], queryFn: () => getFunnelSummary() });
  const retention = useQuery({ queryKey: ["retention-summary"], queryFn: () => getRetentionSummary() });
  const keywords = useQuery({ queryKey: ["keywords-summary"], queryFn: () => getKeywordsSummary() });
  const metaAds = useQuery({ queryKey: ["meta-ads-summary"], queryFn: () => getMetaAdsSummary() });

  const shopifyMargin = ue.data?.channels.find((c) => c.channel === "shopify");
  const amazonMargin = ue.data?.channels.find((c) => c.channel === "amazon");
  const problemQueries = keywords.data?.queries.filter((q) => q.issue !== "healthy").length ?? 0;
  const actionableAdsets = metaAds.data?.adsets.filter((a) => a.rule === "scale" || a.rule === "cut" || a.rule === "pause").length ?? 0;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-ink">Overview</h2>
        <p className="text-sm text-ink-muted">The headline number from each module. Open one in the sidebar for the detail behind it.</p>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <HeadlineCard
          title="Shopify contribution margin"
          loading={ue.isLoading}
          value={shopifyMargin ? formatPct(shopifyMargin.contribution_margin_pct, 1) : "—"}
          sub="Unit Economics"
          tone={shopifyMargin && shopifyMargin.contribution_margin >= 0 ? "positive" : "negative"}
        />
        <HeadlineCard
          title="Amazon contribution margin"
          loading={ue.isLoading}
          value={amazonMargin ? formatPct(amazonMargin.contribution_margin_pct, 1) : "—"}
          sub="Unit Economics"
          tone={amazonMargin && amazonMargin.contribution_margin >= 0 ? "positive" : "negative"}
        />
        <HeadlineCard
          title="Shopify conversion rate"
          loading={funnel.isLoading}
          value={funnel.data ? formatPct(funnel.data.shopify.completed_checkout_rate, 1) : "—"}
          sub="Funnel — sessions to purchase"
        />
        <HeadlineCard
          title="Repeat purchase rate"
          loading={retention.isLoading}
          value={retention.data?.has_data ? formatPct(retention.data.overall.repeat_rate, 0) : "—"}
          sub="Retention — Shopify customers who ordered again"
        />
        <HeadlineCard
          title="Keywords needing a fix"
          loading={keywords.isLoading}
          value={String(problemQueries)}
          sub="Amazon Keywords — listing or price/review problems"
          tone={problemQueries > 0 ? "negative" : "positive"}
        />
        <HeadlineCard
          title="Meta adsets needing action"
          loading={metaAds.isLoading}
          value={String(actionableAdsets)}
          sub="Meta Ads — scale, cut, or pause recommended"
          tone={actionableAdsets > 0 ? "negative" : "neutral"}
        />
      </div>
    </div>
  );
}
