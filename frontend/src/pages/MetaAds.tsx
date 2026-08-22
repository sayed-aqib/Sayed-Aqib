import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getCampaignScoringSummary, type AdPlatform, type AdsetRecommendation } from "../lib/api";
import { formatINR, formatNumber, formatPct } from "../lib/format";
import { Card } from "../components/Card";
import { GlassCard } from "../components/GlassCard";
import { InfoTip } from "../components/InfoTip";
import { RuleBadge } from "../components/RuleBadge";
import { EmptyState } from "../components/EmptyState";
import { CardSkeleton } from "../components/Skeleton";

const RULE_GLOW: Record<AdsetRecommendation["rule"], "positive" | "negative" | "caution" | "neutral"> = {
  scale: "positive",
  hold: "neutral",
  cut: "negative",
  pause: "negative",
  insufficient_data: "caution",
  too_new: "neutral",
};

const PLATFORM_META: Record<
  AdPlatform,
  {
    label: string;
    channelLabel: string;
    emptyTitle: string;
    emptyInstruction: string;
    breakevenDefinition: string;
    blendedLabel: string;
    blendedDefinition: string;
    platformRoasDefinition: string;
  }
> = {
  meta: {
    label: "Meta Ads",
    channelLabel: "Shopify",
    emptyTitle: "No Meta ads data yet",
    emptyInstruction: "Drop a Meta Ads insights export into data/raw/meta_ads_insights/.",
    breakevenDefinition:
      "1 ÷ contribution margin ratio, computed fresh from the last 28 days of Shopify orders. Every adset is judged against this line — it moves whenever costs move.",
    blendedLabel: "Blended MER",
    blendedDefinition:
      "Total Shopify revenue ÷ total Meta spend, last 28 days — the honest number, since Meta over-attributes to itself.",
    platformRoasDefinition:
      "What Meta itself claims, last 28 days — shown next to blended MER so the gap between them is visible.",
  },
  amazon: {
    label: "Amazon Sponsored Products",
    channelLabel: "Amazon",
    emptyTitle: "No Amazon Sponsored Products data yet",
    emptyInstruction: "Drop an Amazon SP campaign report export into data/raw/amazon_sp_campaign_report/.",
    breakevenDefinition:
      "1 ÷ contribution margin ratio, computed fresh from the last 28 days of Amazon sales. Amazon's own margin, not Shopify's — different fees, different line.",
    blendedLabel: "Blended channel MER",
    blendedDefinition: "Total Amazon revenue ÷ total Sponsored Products spend, last 28 days.",
    platformRoasDefinition:
      "ROAS as Amazon's own ACOS reporting implies it, last 28 days — shown next to blended MER so the gap is visible.",
  },
  flipkart: {
    label: "Flipkart Ads",
    channelLabel: "Flipkart",
    emptyTitle: "No Flipkart Ads data yet",
    emptyInstruction: "Drop a Flipkart Ads campaign report export into data/raw/flipkart_ads_campaign_report/.",
    breakevenDefinition:
      "1 ÷ contribution margin ratio, computed fresh from the last 28 days of Flipkart sales — Flipkart's own commission and shipping fees, not Amazon's or Shopify's.",
    blendedLabel: "Blended channel MER",
    blendedDefinition: "Total Flipkart revenue ÷ total Flipkart Ads spend, last 28 days.",
    platformRoasDefinition:
      "Direct ROAS as Flipkart Ads reports it, last 28 days — shown next to blended MER so the gap is visible.",
  },
};

function AdsetCard({ row, breakevenRoas }: { row: AdsetRecommendation; breakevenRoas: number | null }) {
  const roasVsBreakeven = breakevenRoas ? row.roas_7d / breakevenRoas : null;

  return (
    <GlassCard glow={RULE_GLOW[row.rule]}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs text-ink-muted">{row.campaign_name}</p>
          <h3 className="font-semibold text-ink">{row.adset_name}</h3>
        </div>
        <RuleBadge rule={row.rule} />
      </div>

      <div className="mt-3 grid grid-cols-4 gap-3 text-sm">
        <div>
          <p className="text-xs text-ink-muted">Spend (7d)</p>
          <p className="tabular-nums text-ink">{formatINR(row.spend_7d)}</p>
        </div>
        <div>
          <p className="text-xs text-ink-muted">Purchases (7d)</p>
          <p className="tabular-nums text-ink">{formatNumber(row.purchases_7d)}</p>
        </div>
        <div>
          <p className="text-xs text-ink-muted">ROAS (7d)</p>
          <p className="tabular-nums text-ink">
            {row.roas_7d.toFixed(2)}
            {roasVsBreakeven !== null && (
              <span className="ml-1 text-xs text-ink-muted">({roasVsBreakeven.toFixed(1)}x break-even)</span>
            )}
          </p>
        </div>
        <div>
          <p className="text-xs text-ink-muted">Frequency</p>
          <p className={`tabular-nums ${row.is_fatigued ? "text-caution" : "text-ink"}`}>
            {row.frequency_7d !== null ? row.frequency_7d.toFixed(2) : "—"}
            {row.is_fatigued && <span className="ml-1 text-xs">creative tiring</span>}
          </p>
        </div>
      </div>

      <div className="mt-3 flex items-center justify-between border-t border-border pt-3 text-sm">
        <p className="text-ink-muted">
          {row.reasoning}
          {row.recommended_change_pct !== null && (
            <span className="ml-1 text-ink">
              → {row.recommended_change_pct > 0 ? "+" : ""}
              {formatPct(row.recommended_change_pct, 0)}
              {row.capped_from_pct !== null && (
                <span className="text-ink-muted"> (rule said {formatPct(row.capped_from_pct, 0)}, capped by guardrail)</span>
              )}
            </span>
          )}
        </p>
        <span className="ml-3 shrink-0 text-xs text-ink-muted">confidence: {row.confidence}</span>
      </div>
    </GlassCard>
  );
}

export function MetaAds() {
  const [platform, setPlatform] = useState<AdPlatform>("meta");
  const meta = PLATFORM_META[platform];

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["campaign-scoring", platform],
    queryFn: () => getCampaignScoringSummary(platform),
  });

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-ink">Ad Campaigns</h2>
        <p className="text-sm text-ink-muted">
          Advisory only — this recommends, nothing is ever pushed to any ad platform automatically. Same rule engine
          for every platform, each judged against its own channel's break-even.
        </p>
      </div>

      <div className="flex gap-1.5">
        {(Object.keys(PLATFORM_META) as AdPlatform[]).map((p) => (
          <button
            key={p}
            onClick={() => setPlatform(p)}
            className={`rounded-full border px-3.5 py-1.5 text-sm transition-colors ${
              platform === p
                ? "border-brand/15 bg-white/70 font-medium text-brand shadow-[0_1px_3px_rgba(31,64,50,0.12)]"
                : "border-transparent text-ink-muted hover:bg-white/40 hover:text-ink"
            }`}
          >
            {PLATFORM_META[p].label}
          </button>
        ))}
      </div>

      {isLoading && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <CardSkeleton lines={1} />
            <CardSkeleton lines={1} />
            <CardSkeleton lines={1} />
          </div>
          <CardSkeleton lines={3} />
          <CardSkeleton lines={3} />
        </div>
      )}

      {!isLoading && (isError || !data) && (
        <Card>
          <p className="text-sm text-negative">Couldn't load {meta.label}: {(error as Error)?.message}</p>
        </Card>
      )}

      {!isLoading && data && data.adsets.length === 0 && (
        <EmptyState title={meta.emptyTitle} instruction={meta.emptyInstruction} />
      )}

      {!isLoading && data && data.adsets.length > 0 && (
        <>
          <p className="text-xs text-ink-muted">As of {data.as_of}.</p>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <GlassCard>
              <div className="flex items-center gap-1 text-sm text-ink-muted">
                Break-even ROAS
                <InfoTip>{meta.breakevenDefinition}</InfoTip>
              </div>
              <p className="tabular-nums mt-1 text-2xl font-semibold text-ink">
                {data.breakeven.breakeven_roas !== null ? `${data.breakeven.breakeven_roas.toFixed(2)}x` : "—"}
              </p>
              <p className="tabular-nums mt-1 text-xs text-ink-muted">
                allowable CPA {formatINR(data.breakeven.allowable_cpa)} · margin{" "}
                {formatPct(data.breakeven.contribution_margin_ratio, 0)}
              </p>
            </GlassCard>
            <GlassCard>
              <div className="flex items-center gap-1 text-sm text-ink-muted">
                {meta.blendedLabel}
                <InfoTip>{meta.blendedDefinition}</InfoTip>
              </div>
              <p className="tabular-nums mt-1 text-2xl font-semibold text-ink">
                {data.blended_mer !== null ? `${data.blended_mer.toFixed(2)}x` : "—"}
              </p>
            </GlassCard>
            <GlassCard>
              <div className="flex items-center gap-1 text-sm text-ink-muted">
                Platform-reported ROAS
                <InfoTip>{meta.platformRoasDefinition}</InfoTip>
              </div>
              <p className="tabular-nums mt-1 text-2xl font-semibold text-ink">
                {data.platform_roas_28d !== null ? `${data.platform_roas_28d.toFixed(2)}x` : "—"}
              </p>
            </GlassCard>
          </div>

          <div className="space-y-3">
            {data.adsets.map((row) => (
              <AdsetCard key={`${row.campaign_name}-${row.adset_name}`} row={row} breakevenRoas={data.breakeven.breakeven_roas} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
