import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getCostsSummary, saveCostVersion, type CostVersion, type ProductRef } from "../lib/api";
import { formatINR } from "../lib/format";
import { Card } from "../components/Card";
import { GlassCard } from "../components/GlassCard";
import { InfoTip } from "../components/InfoTip";
import { CardSkeleton } from "../components/Skeleton";

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

function emptyVersionFor(products: ProductRef[]): CostVersion {
  const zeros = Object.fromEntries(products.map((p) => [p.product_id, 0]));
  return {
    effective_date: todayISO(),
    cogs_per_unit: { ...zeros },
    packaging_per_unit: { ...zeros },
    shipping_shopify_per_order: 0,
    shopify_gateway_pct: 0,
    shopify_gateway_fixed: 0,
    amazon_referral_pct: 0,
    amazon_fba_per_unit: 0,
    returns_provision_pct: { shopify: 0, amazon: 0 },
  };
}

function NumberField({
  label,
  value,
  onChange,
  suffix,
  step = 1,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  suffix?: string;
  step?: number;
}) {
  return (
    <label className="flex items-center justify-between gap-3 text-sm">
      <span className="text-ink-muted">{label}</span>
      <span className="flex items-center gap-1">
        <input
          type="number"
          step={step}
          value={Number.isFinite(value) ? value : 0}
          onChange={(e) => onChange(e.target.valueAsNumber || 0)}
          className="tabular-nums w-24 rounded-md border border-border bg-white/70 px-2 py-1 text-right text-ink outline-none focus:border-brand"
        />
        {suffix && <span className="w-4 text-xs text-ink-muted">{suffix}</span>}
      </span>
    </label>
  );
}

export function Settings() {
  const queryClient = useQueryClient();
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["costs-summary"],
    queryFn: () => getCostsSummary(),
  });

  const [form, setForm] = useState<CostVersion | null>(null);
  const [savedNote, setSavedNote] = useState<string | null>(null);

  useEffect(() => {
    if (!data || form) return;
    const current = data.versions.find((v) => v.effective_date === data.current_effective_date);
    setForm(current ? { ...current, effective_date: todayISO() } : emptyVersionFor(data.products));
  }, [data, form]);

  const mutation = useMutation({
    mutationFn: (version: CostVersion) => saveCostVersion(version),
    onSuccess: (updated) => {
      queryClient.setQueryData(["costs-summary"], updated);
      queryClient.invalidateQueries({ queryKey: ["unit-economics-summary"] });
      queryClient.invalidateQueries({ queryKey: ["meta-ads-summary"] });
      setSavedNote(`Saved. Effective ${updated.versions[updated.versions.length - 1].effective_date}.`);
    },
  });

  if (isLoading || !form) {
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
        <p className="text-sm text-negative">Couldn't load costs: {(error as Error)?.message}</p>
      </Card>
    );
  }

  const productName = (id: string) => data.products.find((p) => p.product_id === id)?.name ?? id;

  const setCogs = (id: string, v: number) => setForm((f) => f && { ...f, cogs_per_unit: { ...f.cogs_per_unit, [id]: v } });
  const setPackaging = (id: string, v: number) =>
    setForm((f) => f && { ...f, packaging_per_unit: { ...f.packaging_per_unit, [id]: v } });

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-ink">Costs</h2>
        <p className="text-sm text-ink-muted">
          What Hayah Care actually pays, per unit and per order. Every margin number on this site — Unit Economics,
          break-even ROAS — is computed from these figures. Nothing here is guessed.
        </p>
      </div>

      <GlassCard glow="caution">
        <div className="flex items-center gap-1 text-sm text-ink-muted">
          How versioning works
          <InfoTip>
            Saving here adds a new dated cost version instead of overwriting the old one — orders from before this
            date keep pricing at the old figures, so editing a cost today never silently changes last month's
            numbers.
          </InfoTip>
        </div>
        <p className="mt-1 text-sm text-ink">
          Currently effective from <span className="font-medium">{data.current_effective_date}</span>. Changes you
          save below take effect from the date you choose — usually today.
        </p>
      </GlassCard>

      <Card>
        <h3 className="font-semibold text-ink">Per-SKU costs</h3>
        <p className="text-xs text-ink-muted">What we pay to make and pack each unit sold.</p>
        <div className="mt-3 space-y-3 divide-y divide-border">
          {data.products.map((p) => (
            <div key={p.product_id} className="grid grid-cols-[1fr_auto_auto] items-center gap-4 pt-3 first:pt-0">
              <span className="text-sm text-ink">{p.name}</span>
              <NumberField
                label="COGS"
                value={form.cogs_per_unit[p.product_id] ?? 0}
                onChange={(v) => setCogs(p.product_id, v)}
                suffix="₹"
              />
              <NumberField
                label="Packaging"
                value={form.packaging_per_unit[p.product_id] ?? 0}
                onChange={(v) => setPackaging(p.product_id, v)}
                suffix="₹"
              />
            </div>
          ))}
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Card>
          <h3 className="font-semibold text-ink">Shipping &amp; fees</h3>
          <div className="mt-3 space-y-2.5">
            <NumberField
              label="Shopify shipping per order"
              value={form.shipping_shopify_per_order}
              onChange={(v) => setForm((f) => f && { ...f, shipping_shopify_per_order: v })}
              suffix="₹"
            />
            <NumberField
              label="Shopify gateway fee"
              value={Math.round(form.shopify_gateway_pct * 1000) / 10}
              onChange={(v) => setForm((f) => f && { ...f, shopify_gateway_pct: v / 100 })}
              suffix="%"
              step={0.1}
            />
            <NumberField
              label="Shopify gateway fixed fee"
              value={form.shopify_gateway_fixed}
              onChange={(v) => setForm((f) => f && { ...f, shopify_gateway_fixed: v })}
              suffix="₹"
            />
            <NumberField
              label="Amazon referral fee"
              value={Math.round(form.amazon_referral_pct * 1000) / 10}
              onChange={(v) => setForm((f) => f && { ...f, amazon_referral_pct: v / 100 })}
              suffix="%"
              step={0.1}
            />
            <NumberField
              label="Amazon FBA fee per unit"
              value={form.amazon_fba_per_unit}
              onChange={(v) => setForm((f) => f && { ...f, amazon_fba_per_unit: v })}
              suffix="₹"
            />
          </div>
        </Card>

        <Card>
          <h3 className="font-semibold text-ink">Returns provision</h3>
          <p className="text-xs text-ink-muted">A set-aside, as a % of revenue, for orders that come back.</p>
          <div className="mt-3 space-y-2.5">
            <NumberField
              label="Shopify"
              value={Math.round(form.returns_provision_pct.shopify * 1000) / 10}
              onChange={(v) => setForm((f) => f && { ...f, returns_provision_pct: { ...f.returns_provision_pct, shopify: v / 100 } })}
              suffix="%"
              step={0.1}
            />
            <NumberField
              label="Amazon"
              value={Math.round(form.returns_provision_pct.amazon * 1000) / 10}
              onChange={(v) => setForm((f) => f && { ...f, returns_provision_pct: { ...f.returns_provision_pct, amazon: v / 100 } })}
              suffix="%"
              step={0.1}
            />

            <div className="border-t border-border pt-3">
              <label className="flex items-center justify-between gap-3 text-sm">
                <span className="text-ink-muted">Effective from</span>
                <input
                  type="date"
                  value={form.effective_date}
                  onChange={(e) => setForm((f) => f && { ...f, effective_date: e.target.value })}
                  className="rounded-md border border-border bg-white/70 px-2 py-1 text-ink outline-none focus:border-brand"
                />
              </label>
            </div>
          </div>
        </Card>
      </div>

      <div className="flex items-center gap-3">
        <button
          type="button"
          disabled={mutation.isPending}
          onClick={() => {
            setSavedNote(null);
            mutation.mutate(form);
          }}
          className="rounded-full bg-brand px-5 py-2 text-sm font-medium text-white shadow-[0_1px_3px_rgba(31,64,50,0.25)] transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          {mutation.isPending ? "Saving…" : "Save cost version"}
        </button>
        {savedNote && <span className="text-sm text-positive">{savedNote}</span>}
        {mutation.isError && (
          <span className="text-sm text-negative">Couldn't save: {(mutation.error as Error).message}</span>
        )}
      </div>

      <Card>
        <h3 className="font-semibold text-ink">Cost history</h3>
        <p className="text-xs text-ink-muted">Every saved version. Past orders always price at the version effective on their own date.</p>
        <div className="mt-3 space-y-2">
          {[...data.versions]
            .sort((a, b) => (a.effective_date < b.effective_date ? 1 : -1))
            .map((v) => (
              <div key={v.effective_date} className="flex items-center justify-between text-sm">
                <span className="text-ink">{v.effective_date}</span>
                <span className="tabular-nums text-ink-muted">
                  {data.products
                    .slice(0, 2)
                    .map((p) => `${productName(p.product_id)} ${formatINR(v.cogs_per_unit[p.product_id] ?? 0)}`)
                    .join(" · ")}
                </span>
              </div>
            ))}
        </div>
      </Card>
    </div>
  );
}
