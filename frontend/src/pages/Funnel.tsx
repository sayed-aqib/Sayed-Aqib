import { useQuery } from "@tanstack/react-query";
import { getFunnelSummary } from "../lib/api";
import { formatNumber, formatPct } from "../lib/format";
import { Card } from "../components/Card";
import { InfoTip } from "../components/InfoTip";
import { LowConfidenceBadge } from "../components/LowConfidenceBadge";
import { FunnelStep } from "../components/FunnelStep";

export function Funnel() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["funnel-summary"],
    queryFn: () => getFunnelSummary(),
  });

  if (isLoading) {
    return <p className="text-sm text-ink-muted">Loading funnel…</p>;
  }
  if (isError || !data) {
    return (
      <Card>
        <p className="text-sm text-negative">Couldn't load the funnel: {(error as Error)?.message}</p>
      </Card>
    );
  }

  const { shopify, shopify_referrer, amazon } = data;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-ink">Funnel</h2>
        <p className="text-sm text-ink-muted">
          {data.start} to {data.end}. Shopify and Amazon are shown separately — they're different funnels with
          different data.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Card>
          <div className="flex items-start justify-between">
            <h3 className="font-semibold text-ink">Shopify: sessions to purchase</h3>
            {shopify.low_confidence && <LowConfidenceBadge sampleSize={shopify.completed_checkout} />}
          </div>
          <div className="mt-4 space-y-4">
            <FunnelStep label="Sessions" count={shopify.sessions} shareOfSessions={1} isFirst />
            <FunnelStep
              label="Added to cart"
              count={shopify.added_to_cart}
              shareOfSessions={shopify.added_to_cart_rate}
              dropOff={shopify.drop_off_sessions_to_cart}
            />
            <FunnelStep
              label="Reached checkout"
              count={shopify.reached_checkout}
              shareOfSessions={shopify.reached_checkout_rate}
              dropOff={shopify.drop_off_cart_to_checkout}
            />
            <FunnelStep
              label="Completed checkout (purchased)"
              count={shopify.completed_checkout}
              shareOfSessions={shopify.completed_checkout_rate}
              dropOff={shopify.drop_off_checkout_to_purchase}
            />
          </div>

          <div className="mt-5 flex items-center justify-between border-t border-border pt-3 text-sm">
            <span className="flex items-center gap-1 text-ink-muted">
              Paid vs. organic sessions
              <InfoTip>
                Paid = sessions from a referrer with "Ads" in the name (Facebook Ads, Google Ads). Everything else —
                direct, organic search, email, social — counts as organic.
              </InfoTip>
            </span>
            <span className="tabular-nums text-ink">
              {formatPct(shopify_referrer.paid_share, 0)} paid ({formatNumber(shopify_referrer.paid_sessions)} of{" "}
              {formatNumber(shopify_referrer.paid_sessions + shopify_referrer.organic_sessions)})
            </span>
          </div>
        </Card>

        <Card>
          <div className="flex items-center gap-1">
            <h3 className="font-semibold text-ink">Amazon: sessions to units, by product</h3>
            <InfoTip>
              Amazon doesn't give sellers a cart/checkout breakdown like Shopify — this is sessions and unit session %
              (units ordered ÷ sessions) per child ASIN, straight from Detail Page Sales & Traffic.
            </InfoTip>
          </div>
          <div className="mt-4 space-y-3">
            {amazon.map((row) => (
              <div key={row.product_id}>
                <div className="flex items-baseline justify-between text-sm">
                  <span className="flex items-center gap-1.5 text-ink">
                    {row.name}
                    {row.low_confidence && <LowConfidenceBadge sampleSize={row.units_ordered} />}
                  </span>
                  <span className="tabular-nums text-ink">
                    {formatNumber(row.units_ordered)} units / {formatNumber(row.sessions)} sessions
                  </span>
                </div>
                <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-border/60">
                  <div
                    className="h-full rounded-full bg-ink/70"
                    style={{ width: `${Math.min(100, row.unit_session_pct * 100)}%` }}
                  />
                </div>
                <p className="tabular-nums mt-1 text-xs text-ink-muted">
                  {formatPct(row.unit_session_pct, 1)} unit session rate
                </p>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
