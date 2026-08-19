/** A restrained nod to the "premium quality" seal motif — reserved for a
 * genuinely strong number, not decoration. Never placed on a metric that's
 * merely present; only one that's actually good. */
export function SealBadge({ label }: { label: string }) {
  return (
    <span className="inline-flex shrink-0 items-center gap-1 whitespace-nowrap rounded-full border border-brand-gold/40 bg-brand-gold/10 py-0.5 pl-1 pr-2 text-[11px] font-medium text-brand-gold">
      <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
        <circle cx="6" cy="6" r="5.25" stroke="currentColor" strokeWidth="1" />
        <path d="M3.6 6.2 5.1 7.7 8.4 4.2" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      {label}
    </span>
  );
}
