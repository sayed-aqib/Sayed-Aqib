export function LowConfidenceBadge({ sampleSize }: { sampleSize: number }) {
  return (
    <span
      className="rounded border border-caution/40 bg-caution/10 px-1.5 py-0.5 text-[11px] font-medium text-caution"
      title={`Based on only ${sampleSize} — treat this number as directional, not fact.`}
    >
      low confidence · n={sampleSize}
    </span>
  );
}
