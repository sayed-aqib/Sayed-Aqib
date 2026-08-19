import type { ReactNode } from "react";

const GLOW: Record<string, string> = {
  positive: "rgba(45,106,79,0.32)",
  negative: "rgba(179,64,46,0.28)",
  caution: "rgba(181,138,0,0.26)",
  neutral: "",
};

/** Frosted-glass surface with an optional ambient glow tied to the same
 * semantic meaning as the content's own color — reinforces the reading
 * rather than decorating it. Use for stat/summary cards; dense tables stay
 * on the plain opaque Card so small text keeps full contrast. */
export function GlassCard({
  children,
  glow = "neutral",
  className = "",
}: {
  children: ReactNode;
  glow?: "positive" | "negative" | "caution" | "neutral";
  className?: string;
}) {
  const glowColor = GLOW[glow];
  return (
    <div className="relative">
      {glowColor && <div className="pointer-events-none absolute -inset-3 rounded-[28px] blur-2xl" style={{ background: glowColor }} />}
      <div
        className={`relative rounded-xl border border-white/60 bg-white/65 p-4 shadow-[0_1px_2px_rgba(26,26,23,0.04)] backdrop-blur-xl ${className}`}
      >
        {children}
      </div>
    </div>
  );
}
