import { useQuery } from "@tanstack/react-query";
import { getMetaAdsSummary, type AdsetRecommendation } from "../lib/api";
import { formatINR, formatNumber, formatPct } from "../lib/format";
import { Card } from "../components/Card";
import { InfoTip } from "../components/InfoTip";
import { RuleBadge } from "../components/RuleBadge";
import { EmptyState } from "../components/EmptyState";

function AdsetCard({ row, breakevenRoas }: { row: AdsetRecommendation; breakevenRoas: number | null }) {
  const roasVsBreakeven = breakevenRoas ? row.roas_7d / breakevenRoas : null;

  return (
    <Card>
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
            {row.frequency_7d.toFixed(2)}
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
    </Card>
  );
}

export function MetaAds() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["meta-ads-summary"],
    queryFn: () => getMetaAdsSummary(),
  });

  if (isLoading) {
    return <p className="text-sm text-ink-muted">Loading Meta ads…</p>;
  }
  if (isError || !data) {
    return (
      <Card>
        <p className="text-sm text-negative">Couldn't load Meta ads: {(error as Error)?.message}</p>
      </Card>
    );
  }
  if (data.adsets.length === 0) {
    return (
      <div className="space-y-2">
        <h2 className="text-lg font-semibold text-ink">Meta Ads Budget</h2>
        <EmptyState
          title="No Meta ads data yet"
          instruction="Drop a Meta Ads insights export into data/raw/meta_ads_insights/."
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-ink">Meta Ads Budget</h2>
        <p className="text-sm text-ink-muted">
          As of {data.as_of}. Advisory only — this recommends, nothing is ever pushed to Meta automatically.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <Card>
          <div className="flex items-center gap-1 text-sm text-ink-muted">
            Break-even ROAS
            <InfoTip>
              1 ÷ contribution margin ratio, computed fresh from the last 28 days of Shopify orders. Every adset is
              judged against this line — it moves whenever costs move.
            </InfoTip>
          </div>
          <p className="tabular-nums mt-1 text-2xl font-semibold text-ink">
            {data.breakeven.breakeven_roas !== null ? `${data.breakeven.breakeven_roas.toFixed(2)}x` : "—"}
          </p>
          <p className="tabular-nums mt-1 text-xs text-ink-muted">
            allowable CPA {formatINR(data.breakeven.allowable_cpa)} · margin {formatPct(data.breakeven.contribution_margin_ratio, 0)}
          </p>
        </Card>
        <Card>
          <div className="flex items-center gap-1 text-sm text-ink-muted">
            Blended MER
            <InfoTip>Total Shopify revenue ÷ total Meta spend, last 28 days — the honest number, since Meta over-attributes to itself.</InfoTip>
          </div>
          <p className="tabular-nums mt-1 text-2xl font-semibold text-ink">
            {data.blended_mer !== null ? `${data.blended_mer.toFixed(2)}x` : "—"}
          </p>
        </Card>
        <Card>
          <div className="flex items-center gap-1 text-sm text-ink-muted">
            Platform-reported ROAS
            <InfoTip>What Meta itself claims, last 28 days — shown next to blended MER so the gap between them is visible.</InfoTip>
          </div>
          <p className="tabular-nums mt-1 text-2xl font-semibold text-ink">
            {data.platform_roas_28d !== null ? `${data.platform_roas_28d.toFixed(2)}x` : "—"}
          </p>
        </Card>
      </div>

      <div className="space-y-3">
        {data.adsets.map((row) => (
          <AdsetCard key={`${row.campaign_name}-${row.adset_name}`} row={row} breakevenRoas={data.breakeven.breakeven_roas} />
        ))}
      </div>
    </div>
  );
}
