import { useState } from "react";

export function InfoTip({ children }: { children: string }) {
  const [open, setOpen] = useState(false);

  return (
    <span className="relative inline-flex">
      <button
        type="button"
        aria-label="What this number means"
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onClick={() => setOpen((v) => !v)}
        className="flex h-4 w-4 items-center justify-center rounded-full border border-ink-muted/40 text-[10px] leading-none text-ink-muted transition-colors hover:border-brand hover:text-brand"
      >
        i
      </button>
      {open && (
        <span
          role="tooltip"
          className="absolute bottom-full left-1/2 z-10 mb-2 w-56 -translate-x-1/2 rounded-md border border-border border-t-2 border-t-brand-gold bg-panel p-2 text-xs leading-snug text-ink shadow-sm"
        >
          {children}
        </span>
      )}
    </span>
  );
}
