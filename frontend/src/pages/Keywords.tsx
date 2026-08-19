import { useQuery } from "@tanstack/react-query";
import { getKeywordsSummary, type SearchQueryRow } from "../lib/api";
import { formatNumber, formatPct } from "../lib/format";
import { Card } from "../components/Card";
import { InfoTip } from "../components/InfoTip";
import { LowConfidenceBadge } from "../components/LowConfidenceBadge";
import { EmptyState } from "../components/EmptyState";
import { CardSkeleton } from "../components/Skeleton";

function QueryTable({
  rows,
  metricLabel,
  metricValue,
}: {
  rows: SearchQueryRow[];
  metricLabel: string;
  metricValue: (r: SearchQueryRow) => string;
}) {
  if (rows.length === 0) {
    return <p className="text-sm text-ink-muted">None in this window.</p>;
  }
  return (
    <Card className="overflow-x-auto p-0">
      <table className="w-full min-w-[560px] border-collapse text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-ink-muted">
            <th className="px-4 py-2 font-medium">Search query</th>
            <th className="px-3 py-2 text-right font-medium">Impressions</th>
            <th className="px-3 py-2 text-right font-medium">Clicks</th>
            <th className="px-3 py-2 text-right font-medium">Purchases</th>
            <th className="px-3 py-2 text-right font-medium">{metricLabel}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.search_query} className="border-b border-border last:border-0">
              <td className="px-4 py-2 text-ink">
                {r.search_query}
                {r.low_confidence && (
                  <span className="ml-2 align-middle">
                    <LowConfidenceBadge sampleSize={r.purchases} />
                  </span>
                )}
              </td>
              <td className="tabular-nums px-3 py-2 text-right text-ink-muted">{formatNumber(r.impressions)}</td>
              <td className="tabular-nums px-3 py-2 text-right text-ink-muted">{formatNumber(r.clicks)}</td>
              <td className="tabular-nums px-3 py-2 text-right text-ink-muted">{formatNumber(r.purchases)}</td>
              <td className="tabular-nums px-3 py-2 text-right text-caution">{metricValue(r)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

export function Keywords() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["keywords-summary"],
    queryFn: () => getKeywordsSummary(),
  });

  if (isLoading) {
    return (
      <div className="space-y-4">
        <CardSkeleton lines={4} />
        <CardSkeleton lines={4} />
      </div>
    );
  }
  if (isError || !data) {
    return (
      <Card>
        <p className="text-sm text-negative">Couldn't load keywords: {(error as Error)?.message}</p>
      </Card>
    );
  }
  if (data.queries.length === 0) {
    return (
      <div className="space-y-2">
        <h2 className="text-lg font-semibold text-ink">Amazon Keywords</h2>
        <EmptyState
          title="No search query data yet"
          instruction="Drop an Amazon Search Query Performance export into data/raw/amazon_search_query_performance/."
        />
      </div>
    );
  }

  const listingProblems = data.queries
    .filter((r) => r.issue === "listing_or_image_problem")
    .sort((a, b) => b.impressions - a.impressions);
  const priceProblems = data.queries
    .filter((r) => r.issue === "price_or_review_problem")
    .sort((a, b) => b.clicks - a.clicks);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-ink">Amazon Keywords</h2>
        <p className="text-sm text-ink-muted">
          {data.start} to {data.end}. Two different problems, two different fixes — never fixed with the same lever.
        </p>
      </div>

      <div>
        <h3 className="mb-1 flex items-center gap-1 font-semibold text-ink">
          Gets seen, doesn't get clicked
          <InfoTip>
            Impressions here, but a click rate below the median for all our queries — usually a listing or image
            problem: the title, main photo, or price shown in search isn't convincing at a glance.
          </InfoTip>
        </h3>
        <p className="mb-2 text-xs text-ink-muted">Sorted by impressions — fix the listing, not the bid.</p>
        <QueryTable rows={listingProblems} metricLabel="Click rate" metricValue={(r) => formatPct(r.click_rate, 1)} />
      </div>

      <div>
        <h3 className="mb-1 flex items-center gap-1 font-semibold text-ink">
          Gets clicked, doesn't convert
          <InfoTip>
            A healthy click rate, but a purchase rate below the median for all our queries — usually a price or
            review problem: they land on the page and decide not to buy.
          </InfoTip>
        </h3>
        <p className="mb-2 text-xs text-ink-muted">Sorted by clicks — check price and reviews, not the listing.</p>
        <QueryTable rows={priceProblems} metricLabel="Purchase rate" metricValue={(r) => formatPct(r.purchase_rate, 1)} />
      </div>
    </div>
  );
}
