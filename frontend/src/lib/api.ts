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

export interface ShopifyFunnel {
  sessions: number;
  added_to_cart: number;
  reached_checkout: number;
  completed_checkout: number;
  added_to_cart_rate: number;
  reached_checkout_rate: number;
  completed_checkout_rate: number;
  drop_off_sessions_to_cart: number;
  drop_off_cart_to_checkout: number;
  drop_off_checkout_to_purchase: number;
  low_confidence: boolean;
}

export interface ShopifyReferrerSplit {
  paid_sessions: number;
  organic_sessions: number;
  paid_share: number;
}

export interface AmazonProductFunnel {
  product_id: string;
  name: string;
  sessions: number;
  units_ordered: number;
  unit_session_pct: number;
  low_confidence: boolean;
}

export interface FunnelSummary {
  start: string;
  end: string;
  shopify: ShopifyFunnel;
  shopify_referrer: ShopifyReferrerSplit;
  amazon: AmazonProductFunnel[];
}

export function getFunnelSummary(params?: { start?: string; end?: string }): Promise<FunnelSummary> {
  const search = new URLSearchParams();
  if (params?.start) search.set("start", params.start);
  if (params?.end) search.set("end", params.end);
  const qs = search.toString();
  return getJSON(`/api/funnel/summary${qs ? `?${qs}` : ""}`);
}

export interface RepeatRateStat {
  sample_size: number;
  repeat_customers: number;
  repeat_rate: number;
  low_confidence: boolean;
}

export interface RepeatRateBySku extends RepeatRateStat {
  first_sku: string;
  name: string;
}

export interface ReorderGapStat {
  sample_size: number;
  median_days: number | null;
  low_confidence: boolean;
}

export interface CohortRow {
  cohort_month: string;
  months_since_first: number;
  order_count: number;
}

export interface CrossSellStat {
  cohort_size: number;
  converted: number;
  conversion_rate: number;
  low_confidence: boolean;
}

export interface RetentionSummary {
  has_data: boolean;
  overall: RepeatRateStat;
  by_first_sku: RepeatRateBySku[];
  reorder_gap: ReorderGapStat;
  cohorts: CohortRow[];
  cross_sell_from_chukku: CrossSellStat;
}

export function getRetentionSummary(): Promise<RetentionSummary> {
  return getJSON("/api/retention/summary");
}

export interface SearchQueryRow {
  search_query: string;
  impressions: number;
  clicks: number;
  cart_adds: number;
  purchases: number;
  click_rate: number;
  purchase_rate: number;
  impression_share: number;
  conversion_share: number;
  issue: "healthy" | "listing_or_image_problem" | "price_or_review_problem";
  low_confidence: boolean;
}

export interface KeywordsSummary {
  start: string;
  end: string;
  queries: SearchQueryRow[];
}

export function getKeywordsSummary(params?: { start?: string; end?: string }): Promise<KeywordsSummary> {
  const search = new URLSearchParams();
  if (params?.start) search.set("start", params.start);
  if (params?.end) search.set("end", params.end);
  const qs = search.toString();
  return getJSON(`/api/keywords/summary${qs ? `?${qs}` : ""}`);
}
