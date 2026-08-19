import { formatNumber, formatPct } from "../lib/format";

export function FunnelStep({
  label,
  count,
  shareOfSessions,
  dropOff,
  isFirst = false,
}: {
  label: string;
  count: number;
  shareOfSessions: number;
  dropOff?: number;
  isFirst?: boolean;
}) {
  return (
    <div>
      <div className="flex items-baseline justify-between text-sm">
        <span className="text-ink">{label}</span>
        <span className="tabular-nums text-ink">
          {formatNumber(count)} <span className="text-ink-muted">({formatPct(shareOfSessions, 1)} of sessions)</span>
        </span>
      </div>
      <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-border/60">
        <div
          className="h-full rounded-full bg-ink/70"
          style={{ width: `${Math.min(100, shareOfSessions * 100)}%` }}
        />
      </div>
      {!isFirst && dropOff !== undefined && (
        <p className="tabular-nums mt-1 text-xs text-negative">{formatPct(dropOff, 1)} drop-off from the step before</p>
      )}
    </div>
  );
}
