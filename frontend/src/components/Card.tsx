import type { ReactNode } from "react";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-xl border border-border bg-panel p-4 shadow-[0_1px_2px_rgba(26,26,23,0.04)] ${className}`}>
      {children}
    </div>
  );
}
