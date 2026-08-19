export interface ChannelSummary {
  channel: "shopify" | "amazon";
  sample_size: number;
  low_confidence: boolean;
  net_revenue: number;
  contribution_margin: number;
  contribution_margin_pct: number;
}

export interface SkuSummary {
  product_id: string;
  name: string;
  channel: "shopify" | "amazon";
  net_revenue: number;
  cogs: number;
  packaging: number;
  shipping: number;
  fees: number;
  returns_provision: number;
  contribution_before_ad_spend: number;
  allocated_ad_spend: number;
  contribution_margin: number;
  contribution_margin_pct: number;
  units: number;
  low_confidence: boolean;
}

export interface UnitEconomicsSummary {
  start: string;
  end: string;
  channels: ChannelSummary[];
  skus: SkuSummary[];
}

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) {
    throw new Error(`${path} failed: ${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export function getUnitEconomicsSummary(params?: { start?: string; end?: string }): Promise<UnitEconomicsSummary> {
  const search = new URLSearchParams();
  if (params?.start) search.set("start", params.start);
  if (params?.end) search.set("end", params.end);
  const qs = search.toString();
  return getJSON(`/api/unit-economics/summary${qs ? `?${qs}` : ""}`);
}
