type IconProps = { className?: string };
const common = { width: 18, height: 18, viewBox: "0 0 18 18", fill: "none", stroke: "currentColor", strokeWidth: 1.5, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };

export function OverviewIcon({ className }: IconProps) {
  return (
    <svg {...common} className={className}>
      <rect x="2.5" y="2.5" width="5.5" height="5.5" rx="1" />
      <rect x="10" y="2.5" width="5.5" height="5.5" rx="1" />
      <rect x="2.5" y="10" width="5.5" height="5.5" rx="1" />
      <rect x="10" y="10" width="5.5" height="5.5" rx="1" />
    </svg>
  );
}

export function CoinsIcon({ className }: IconProps) {
  return (
    <svg {...common} className={className}>
      <ellipse cx="9" cy="5" rx="5.5" ry="2.5" />
      <path d="M3.5 5v4c0 1.4 2.46 2.5 5.5 2.5s5.5-1.1 5.5-2.5V5" />
      <path d="M3.5 9v4c0 1.4 2.46 2.5 5.5 2.5s5.5-1.1 5.5-2.5V9" />
    </svg>
  );
}

export function FunnelIcon({ className }: IconProps) {
  return (
    <svg {...common} className={className}>
      <path d="M2.5 3h13l-4.75 5.7v4.55L7.75 15V8.7z" strokeLinejoin="round" />
    </svg>
  );
}

export function RetentionIcon({ className }: IconProps) {
  return (
    <svg {...common} className={className}>
      <path d="M14.5 9a5.5 5.5 0 1 1-1.75-4.02" />
      <path d="M14.5 2.5V6H11" />
    </svg>
  );
}

export function SearchIcon({ className }: IconProps) {
  return (
    <svg {...common} className={className}>
      <circle cx="8" cy="8" r="5" />
      <path d="M15.5 15.5 12 12" />
    </svg>
  );
}

export function MegaphoneIcon({ className }: IconProps) {
  return (
    <svg {...common} className={className}>
      <path d="M2.5 7.5v3a1 1 0 0 0 1 1H5l1.2 3.6a1 1 0 0 0 1 .7H8v-4" />
      <path d="M5 7.5 12.5 4a.5.5 0 0 1 .7.45v9.1a.5.5 0 0 1-.7.45L5 10.5z" strokeLinejoin="round" />
      <path d="M15.5 7v3.5" />
    </svg>
  );
}

export function GearIcon({ className }: IconProps) {
  return (
    <svg {...common} className={className}>
      <circle cx="9" cy="9" r="2.5" />
      <path d="M9 2.8v1.6M9 13.6v1.6M15.2 9h-1.6M4.4 9H2.8M13.15 4.85l-1.13 1.13M5.98 12.02l-1.13 1.13M13.15 13.15l-1.13-1.13M5.98 5.98 4.85 4.85" />
    </svg>
  );
}
