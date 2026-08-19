export function BrandMark({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" fill="none" aria-hidden="true">
      <path
        d="M10 2C10 2 15.5 5 15.5 10.5C15.5 14.6 13 17 10 18C7 17 4.5 14.6 4.5 10.5C4.5 5 10 2 10 2Z"
        fill="var(--color-brand)"
      />
      <path d="M10 4.5V16" stroke="var(--color-surface)" strokeWidth="0.75" strokeLinecap="round" opacity="0.5" />
      <circle cx="10" cy="9" r="1.3" fill="var(--color-brand-gold)" />
    </svg>
  );
}
