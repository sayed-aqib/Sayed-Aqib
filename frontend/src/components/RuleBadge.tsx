import type { MetaRule } from "../lib/api";

const STYLES: Record<MetaRule, string> = {
  scale: "border-positive/40 bg-positive/10 text-positive",
  hold: "border-border bg-border/40 text-ink-muted",
  cut: "border-negative/40 bg-negative/10 text-negative",
  pause: "border-negative/50 bg-negative/15 text-negative",
  insufficient_data: "border-caution/40 bg-caution/10 text-caution",
  too_new: "border-border bg-border/40 text-ink-muted",
};

const LABELS: Record<MetaRule, string> = {
  scale: "Scale +20%",
  hold: "Hold",
  cut: "Cut",
  pause: "Pause — flag for review",
  insufficient_data: "Insufficient data",
  too_new: "Too new to judge",
};

export function RuleBadge({ rule }: { rule: MetaRule }) {
  return (
    <span className={`rounded border px-2 py-0.5 text-xs font-medium ${STYLES[rule]}`}>{LABELS[rule]}</span>
  );
}
