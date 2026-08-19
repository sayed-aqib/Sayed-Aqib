import { useQuery } from "@tanstack/react-query";
import { getUnitEconomicsSummary, getFunnelSummary, getRetentionSummary, getKeywordsSummary, getMetaAdsSummary } from "../lib/api";
import { formatPct } from "../lib/format";
import { SealBadge } from "../components/SealBadge";

// Ambient glow tied to the same semantic meaning as the number's text color —
// ties into the ink/positive/negative palette rather than an arbitrary hue,
// so the glass treatment reinforces the reading instead of decorating it.
const GLOW: Record<string, string | null> = {
  positive: "rgba(45,106,79,0.32)",
  negative: "rgba(179,64,46,0.28)",
  neutral: null,
};

function HeadlineCard({
  title,
  loading,
  value,
  sub,
  tone = "neutral",
  seal,
}: {
  title: string;
  loading: boolean;
  value: string;
  sub: string;
  tone?: "positive" | "negative" | "neutral";
  seal?: string;
}) {
  const color = tone === "positive" ? "text-positive" : tone === "negative" ? "text-negative" : "text-ink";
  const glow = GLOW[tone];
  return (
    <div className="relative">
      {glow && <div className="pointer-events-none absolute -inset-3 rounded-[28px] blur-2xl" style={{ background: glow }} />}
      <div className="relative rounded-xl border border-white/60 bg-white/65 p-4 shadow-[0_1px_2px_rgba(26,26,23,0.04)] backdrop-blur-xl">
        <div className="flex items-start justify-between gap-2">
          <p className="min-w-0 text-sm text-ink-muted">{title}</p>
          {!loading && seal && <SealBadge label={seal} />}
        </div>
        <p className={`tabular-nums mt-1 text-2xl font-semibold ${loading ? "text-ink-muted" : color}`}>
          {loading ? "…" : value}
        </p>
        <p className="mt-1 text-xs text-ink-muted">{sub}</p>
      </div>
    </div>
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
      <div className="overflow-hidden rounded-xl border border-border bg-[linear-gradient(120deg,#26493a_0%,#3a5f4a_55%,#2f4f3d_100%)] px-6 py-6 shadow-sm">
        <h2 className="text-xl font-bold tracking-tight text-white">Growth Snapshot</h2>
        <p className="mt-1 max-w-xl text-sm text-white/80">
          The headline number from each module, all in one place. Open a page in the sidebar for the full detail
          behind any of these.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <HeadlineCard
          title="Shopify contribution margin"
          loading={ue.isLoading}
          value={shopifyMargin ? formatPct(shopifyMargin.contribution_margin_pct, 1) : "—"}
          sub="Unit Economics"
          tone={shopifyMargin && shopifyMargin.contribution_margin >= 0 ? "positive" : "negative"}
          seal={shopifyMargin && shopifyMargin.contribution_margin_pct >= 0.3 ? "Healthy margin" : undefined}
        />
        <HeadlineCard
          title="Amazon contribution margin"
          loading={ue.isLoading}
          value={amazonMargin ? formatPct(amazonMargin.contribution_margin_pct, 1) : "—"}
          sub="Unit Economics"
          tone={amazonMargin && amazonMargin.contribution_margin >= 0 ? "positive" : "negative"}
          seal={amazonMargin && amazonMargin.contribution_margin_pct >= 0.3 ? "Healthy margin" : undefined}
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
          seal={retention.data?.has_data && retention.data.overall.repeat_rate >= 0.35 ? "Strong retention" : undefined}
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

      <div>
        <h3 className="mb-3 font-semibold text-ink">Our Products</h3>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {[
            { src: "nuts-seeds-supermix.png", name: "Nuts & Seeds Supermix", note: "400g · Shopify + Amazon" },
            { src: "moms-supermix.png", name: "Mom's Supermix", note: "400g · Shopify + Amazon" },
            { src: "chukku-kaappi-powder.png", name: "Chukku Kappi Powder", note: "2-pack · Shopify" },
          ].map((p) => (
            <div key={p.src} className="overflow-hidden rounded-xl border border-white/60 bg-white/70 shadow-sm backdrop-blur-xl">
              <img src={`/images/${p.src}`} alt={`Hayah Care ${p.name}`} className="aspect-[4/5] w-full object-cover" />
              <div className="p-3">
                <p className="text-sm font-medium text-ink">{p.name}</p>
                <p className="text-xs text-ink-muted">{p.note}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
