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
from backend.metrics.retention import (
    cross_sell_from_chukku,
    customer_purchase_sequence,
    monthly_cohorts,
    reorder_gap_stats,
    repeat_purchase_rate,
    repeat_purchase_rate_by_first_sku,
)
from backend.metrics.unit_economics import (
    amazon_sku_day_economics,
    apply_ad_spend,
    channel_summary,
    load_costs_config,
    rollup,
    shopify_line_economics,
)

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"
DEFAULT_COSTS_PATH = CONFIG_DIR / "costs.yaml"

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
