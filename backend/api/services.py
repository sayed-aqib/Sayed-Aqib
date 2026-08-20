"""Glue between the warehouse (backend/api/repo.py) and the pure metric
functions (backend/metrics). Routers call these and just serialize the
result — no math happens here beyond assembling frames and shaping the
response.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import duckdb
import pandas as pd

from backend.api import repo
from backend.metrics.funnel import amazon_funnel_by_product, shopify_funnel, shopify_referrer_split
from backend.metrics.keywords import classify_search_queries
from backend.metrics.meta_ads import (
    breakeven_economics,
    creative_fatigue_flags,
    load_meta_rules,
    recommend_budget_actions,
    rolling_adset_metrics,
)
from backend.metrics.retention import (
    cross_sell_from_chukku,
    customer_purchase_sequence,
    monthly_cohorts,
    reorder_gap_stats,
    repeat_purchase_rate,
    repeat_purchase_rate_by_first_sku,
)
from backend.metrics.unit_economics import (
    CostVersion,
    amazon_sku_day_economics,
    apply_ad_spend,
    channel_summary,
    load_costs_config,
    rollup,
    shopify_line_economics,
    upsert_cost_version,
)

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"
DEFAULT_COSTS_PATH = CONFIG_DIR / "costs.yaml"
DEFAULT_META_RULES_PATH = CONFIG_DIR / "meta_rules.yaml"

EMPTY_ECON_COLS = [
    "product_id", "net_revenue", "cogs", "packaging", "shipping", "fees",
    "returns_provision", "contribution_before_ad_spend", "allocated_ad_spend",
    "contribution_margin", "contribution_margin_pct", "units",
]


def unit_economics_summary(
    con: duckdb.DuckDBPyConnection,
    start: date,
    end: date,
    costs_path: str | Path = DEFAULT_COSTS_PATH,
    min_sample: int = 30,
) -> dict:
    costs = load_costs_config(costs_path)
    products = repo.get_products(con)
    product_names = dict(zip(products["product_id"], products["name"]))

    orders_df, items_df = repo.get_shopify_orders_and_items(con, start, end)
    traffic_df = repo.get_amazon_traffic(con, start, end)
    shopify_ad_spend = repo.get_ad_spend_total(con, "meta", start, end)
    amazon_ad_spend = repo.get_ad_spend_total(con, "amazon", start, end)

    if not items_df.empty:
        shopify_lines = apply_ad_spend(
            shopify_line_economics(orders_df, items_df, costs), shopify_ad_spend, weight_col="ad_weight"
        )
        shopify_by_order = rollup(shopify_lines, "order_id")
        shopify_by_sku = rollup(shopify_lines, "product_id", extra_sum_cols=["quantity"]).rename(
            columns={"quantity": "units"}
        )
        shopify_by_sku["channel"] = "shopify"
    else:
        shopify_by_order = pd.DataFrame(columns=["order_id", "net_revenue", "contribution_margin"])
        shopify_by_sku = pd.DataFrame(columns=EMPTY_ECON_COLS + ["channel"])

    if not traffic_df.empty:
        amazon_rows = apply_ad_spend(
            amazon_sku_day_economics(traffic_df, costs), amazon_ad_spend, weight_col="units_ordered"
        )
        amazon_by_sku = rollup(amazon_rows, "product_id", extra_sum_cols=["units_ordered"]).rename(
            columns={"units_ordered": "units"}
        )
        amazon_by_sku["channel"] = "amazon"
    else:
        amazon_rows = pd.DataFrame(columns=["net_revenue", "contribution_margin", "units_ordered"])
        amazon_by_sku = pd.DataFrame(columns=EMPTY_ECON_COLS + ["channel"])

    channels = channel_summary(shopify_by_order, amazon_rows, min_sample=min_sample)

    sku_df = pd.concat([shopify_by_sku, amazon_by_sku], ignore_index=True, sort=False)
    if not sku_df.empty:
        sku_df["low_confidence"] = sku_df["units"] < min_sample
        sku_df["name"] = sku_df["product_id"].map(product_names).fillna(sku_df["product_id"])

    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "channels": channels.to_dict(orient="records"),
        "skus": sku_df.to_dict(orient="records") if not sku_df.empty else [],
    }


def _cost_version_out(v: CostVersion) -> dict:
    return {
        "effective_date": v.effective_date.isoformat(),
        "cogs_per_unit": v.cogs_per_unit,
        "packaging_per_unit": v.packaging_per_unit,
        "shipping_shopify_per_order": v.shipping_shopify_per_order,
        "shopify_gateway_pct": v.shopify_gateway_pct,
        "shopify_gateway_fixed": v.shopify_gateway_fixed,
        "amazon_referral_pct": v.amazon_referral_pct,
        "amazon_fba_per_unit": v.amazon_fba_per_unit,
        "returns_provision_pct": v.returns_provision_pct,
    }


def costs_summary(con: duckdb.DuckDBPyConnection, costs_path: str | Path = DEFAULT_COSTS_PATH) -> dict:
    costs = load_costs_config(costs_path)
    products = repo.get_products(con)
    today = date.today()
    return {
        "versions": [_cost_version_out(v) for v in costs.versions],
        "current_effective_date": costs.for_date(today).effective_date.isoformat(),
        "products": products[["product_id", "name"]].to_dict(orient="records"),
    }


def save_cost_version(
    con: duckdb.DuckDBPyConnection,
    version: CostVersion,
    costs_path: str | Path = DEFAULT_COSTS_PATH,
) -> dict:
    upsert_cost_version(costs_path, version)
    return costs_summary(con, costs_path)


# A funnel step is a count of conversions, not revenue — 3 conversions is
# the brief's own bar for "don't trust this number yet" in that context,
# distinct from the 30-order bar used for revenue confidence above.
FUNNEL_MIN_SAMPLE = 3


def funnel_summary(con: duckdb.DuckDBPyConnection, start: date, end: date) -> dict:
    products = repo.get_products(con)
    product_names = dict(zip(products["product_id"], products["name"]))

    funnel_df = repo.get_shopify_funnel_daily(con, start, end)
    referrer_df = repo.get_shopify_referrer_sessions(con, start, end)
    traffic_df = repo.get_amazon_traffic(con, start, end)

    shopify = shopify_funnel(funnel_df, min_sample=FUNNEL_MIN_SAMPLE)
    referrer = shopify_referrer_split(referrer_df) if not referrer_df.empty else {
        "paid_sessions": 0, "organic_sessions": 0, "paid_share": 0.0,
    }

    if not traffic_df.empty:
        amazon_df = amazon_funnel_by_product(traffic_df, min_sample=FUNNEL_MIN_SAMPLE)
        amazon_df["name"] = amazon_df["product_id"].map(product_names).fillna(amazon_df["product_id"])
        amazon = amazon_df.to_dict(orient="records")
    else:
        amazon = []

    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "shopify": shopify,
        "shopify_referrer": referrer,
        "amazon": amazon,
    }


def retention_summary(con: duckdb.DuckDBPyConnection) -> dict:
    """Runs over the warehouse's full order history, not a date window —
    truncating would corrupt "first order" detection for anyone whose first
    order falls outside an arbitrary range. Shopify only; see
    backend/metrics/retention.py for why Amazon can't be included."""
    min_d, max_d = repo.get_warehouse_date_bounds(con)
    if min_d is None:
        return {
            "has_data": False,
            "overall": {"sample_size": 0, "repeat_customers": 0, "repeat_rate": 0.0, "low_confidence": True},
            "by_first_sku": [],
            "reorder_gap": {"sample_size": 0, "median_days": None, "low_confidence": True},
            "cohorts": [],
            "cross_sell_from_chukku": {"cohort_size": 0, "converted": 0, "conversion_rate": 0.0, "low_confidence": True},
        }

    products = repo.get_products(con)
    product_names = dict(zip(products["product_id"], products["name"]))

    orders_df, items_df = repo.get_shopify_orders_and_items(con, min_d, max_d + timedelta(days=1))
    seq = customer_purchase_sequence(orders_df, items_df)

    by_sku = repeat_purchase_rate_by_first_sku(seq, min_sample=3)
    by_sku["name"] = by_sku["first_sku"].map(product_names).fillna(by_sku["first_sku"])

    return {
        "has_data": True,
        "overall": repeat_purchase_rate(seq, min_sample=30),
        "by_first_sku": by_sku.to_dict(orient="records"),
        "reorder_gap": reorder_gap_stats(seq, min_sample=3),
        "cohorts": monthly_cohorts(orders_df).to_dict(orient="records"),
        "cross_sell_from_chukku": cross_sell_from_chukku(seq, orders_df, items_df, min_sample=3),
    }


def keywords_summary(con: duckdb.DuckDBPyConnection, start: date, end: date) -> dict:
    df = repo.get_search_query_weekly(con, start, end)
    if df.empty:
        return {"start": start.isoformat(), "end": end.isoformat(), "queries": []}

    classified = classify_search_queries(df).sort_values("impressions", ascending=False)
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "queries": classified.to_dict(orient="records"),
    }


def meta_ads_summary(
    con: duckdb.DuckDBPyConnection,
    as_of: date,
    costs_path: str | Path = DEFAULT_COSTS_PATH,
    rules_path: str | Path = DEFAULT_META_RULES_PATH,
) -> dict:
    rules = load_meta_rules(rules_path)
    window_7_start = as_of - timedelta(days=7)
    window_28_start = as_of - timedelta(days=28)
    fatigue_lookback_start = as_of - timedelta(days=60)

    daily_7 = repo.get_ad_spend_daily_rows(con, "meta", window_7_start, as_of)
    daily_28 = repo.get_ad_spend_daily_rows(con, "meta", window_28_start, as_of)
    daily_fatigue = repo.get_ad_spend_daily_rows(con, "meta", fatigue_lookback_start, as_of)

    if daily_7.empty:
        return {
            "as_of": as_of.isoformat(),
            "breakeven": {"contribution_margin_ratio": 0.0, "breakeven_roas": None, "allowable_cpa": 0.0, "sample_size": 0},
            "blended_mer": None,
            "platform_roas_28d": None,
            "adsets": [],
        }

    costs = load_costs_config(costs_path)
    orders_28, items_28 = repo.get_shopify_orders_and_items(con, window_28_start, as_of)
    if not items_28.empty:
        order_econ_28 = (
            shopify_line_economics(orders_28, items_28, costs)
            .groupby("order_id")[["net_revenue", "contribution_before_ad_spend"]]
            .sum()
            .reset_index()
        )
    else:
        order_econ_28 = pd.DataFrame(columns=["order_id", "net_revenue", "contribution_before_ad_spend"])
    breakeven = breakeven_economics(order_econ_28)

    metrics_7d = rolling_adset_metrics(daily_7)
    metrics_28d = rolling_adset_metrics(daily_28).set_index(["campaign_name", "adset_name"])
    fatigue = creative_fatigue_flags(daily_fatigue, rules).set_index(["campaign_name", "adset_name"])
    adset_first_seen = repo.get_adset_first_seen(con, "meta")
    adset_age_days = {k: (as_of - v).days for k, v in adset_first_seen.items()}

    recommendations = recommend_budget_actions(metrics_7d, breakeven, rules, adset_age_days).set_index(
        ["campaign_name", "adset_name"]
    )

    total_spend_28d = float(daily_28["spend"].sum())
    total_revenue_28d_platform = float(daily_28["revenue"].sum())
    shopify_revenue_28d = float(order_econ_28["net_revenue"].sum())
    blended_mer = (shopify_revenue_28d / total_spend_28d) if total_spend_28d else None
    platform_roas_28d = (total_revenue_28d_platform / total_spend_28d) if total_spend_28d else None

    adsets = []
    for _, row in metrics_7d.iterrows():
        key = (row["campaign_name"], row["adset_name"])
        rec = recommendations.loc[key]
        fat = fatigue.loc[key] if key in fatigue.index else None
        m28 = metrics_28d.loc[key] if key in metrics_28d.index else None
        adsets.append({
            "campaign_name": row["campaign_name"],
            "adset_name": row["adset_name"],
            "days_live": adset_age_days.get(key, 0),
            "spend_7d": float(row["spend"]),
            "purchases_7d": int(row["purchases"]),
            "revenue_7d": float(row["revenue"]),
            "roas_7d": float(row["roas"]),
            "cpa_7d": None if pd.isna(row["cpa"]) else float(row["cpa"]),
            "cpm_7d": float(row["cpm"]),
            "ctr_7d": float(row["ctr"]),
            "frequency_7d": float(row["frequency"]),
            "new_customer_share_7d": float(row["new_customer_share"]),
            "spend_28d": float(m28["spend"]) if m28 is not None else None,
            "roas_28d": float(m28["roas"]) if m28 is not None else None,
            "is_fatigued": bool(fat["is_fatigued"]) if fat is not None else False,
            "rule": rec["rule"],
            "recommended_change_pct": None if pd.isna(rec["recommended_change_pct"]) else float(rec["recommended_change_pct"]),
            "capped_from_pct": None if pd.isna(rec["capped_from_pct"]) else float(rec["capped_from_pct"]),
            "reasoning": rec["reasoning"],
            "confidence": rec["confidence"],
        })

    return {
        "as_of": as_of.isoformat(),
        "breakeven": breakeven,
        "blended_mer": blended_mer,
        "platform_roas_28d": platform_roas_28d,
        "adsets": adsets,
    }
