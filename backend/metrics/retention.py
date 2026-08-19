"""For a 400g consumable, retention is the whole business.

Everything here runs on Shopify data only — Amazon doesn't give sellers
customer identity, so there's no way to tell if an Amazon buyer has ordered
before. That's a real finding, not a gap to paper over: the frontend says so
rather than pretending Amazon repeat rate is zero.
"""

from __future__ import annotations

import pandas as pd


def customer_purchase_sequence(orders_df: pd.DataFrame, items_df: pd.DataFrame) -> pd.DataFrame:
    """One row per customer: order count, first order's date and SKU
    (its highest-value line, so a cross-sold add-on doesn't get credited as
    "first"), and the gap to a second order if there is one."""
    orders = orders_df.dropna(subset=["customer_id"]).sort_values("created_at").copy()

    positive_items = items_df[items_df["quantity"] > 0]
    first_sku_by_order = (
        positive_items.sort_values("line_amount", ascending=False).groupby("order_id")["product_id"].first()
    )
    orders["order_sku"] = orders["order_id"].map(first_sku_by_order)

    rows = []
    for customer_id, g in orders.groupby("customer_id"):
        dates = list(g["created_at"])
        skus = list(g["order_sku"])
        rows.append({
            "customer_id": customer_id,
            "n_orders": len(dates),
            "first_order_at": dates[0],
            "first_sku": skus[0],
            "second_order_at": dates[1] if len(dates) > 1 else None,
            "days_to_second_order": (dates[1] - dates[0]).days if len(dates) > 1 else None,
        })
    return pd.DataFrame(rows)


def repeat_purchase_rate(seq_df: pd.DataFrame, min_sample: int = 30) -> dict:
    sample_size = len(seq_df)
    repeat_customers = int((seq_df["n_orders"] > 1).sum()) if sample_size else 0
    return {
        "sample_size": sample_size,
        "repeat_customers": repeat_customers,
        "repeat_rate": (repeat_customers / sample_size) if sample_size else 0.0,
        "low_confidence": sample_size < min_sample,
    }


def repeat_purchase_rate_by_first_sku(seq_df: pd.DataFrame, min_sample: int = 3) -> pd.DataFrame:
    def agg(g: pd.DataFrame) -> pd.Series:
        n = len(g)
        repeat = int((g["n_orders"] > 1).sum())
        return pd.Series({"sample_size": n, "repeat_customers": repeat, "repeat_rate": (repeat / n) if n else 0.0})

    grouped = seq_df.groupby("first_sku").apply(agg, include_groups=False).reset_index()
    grouped["low_confidence"] = grouped["sample_size"] < min_sample
    return grouped


def reorder_gap_stats(seq_df: pd.DataFrame, min_sample: int = 3) -> dict:
    """Median (not mean — a handful of very fast or very slow reorders
    shouldn't swing the number the founder uses to judge subscription
    viability) days between a customer's first and second order."""
    gaps = seq_df["days_to_second_order"].dropna()
    sample_size = len(gaps)
    return {
        "sample_size": sample_size,
        "median_days": float(gaps.median()) if sample_size else None,
        "low_confidence": sample_size < min_sample,
    }


def monthly_cohorts(orders_df: pd.DataFrame) -> pd.DataFrame:
    """Long-format cohort table: cohort_month (the month of a customer's
    first order), months_since_first, order_count. The frontend pivots this
    into the usual cohort triangle."""
    orders = orders_df.dropna(subset=["customer_id"]).copy()
    orders["order_period"] = orders["created_at"].dt.to_period("M")
    first_period = orders.groupby("customer_id")["order_period"].transform("min")
    orders["cohort_month"] = first_period.astype(str)
    orders["months_since_first"] = (
        (orders["order_period"].dt.year - first_period.dt.year) * 12
        + (orders["order_period"].dt.month - first_period.dt.month)
    )
    return orders.groupby(["cohort_month", "months_since_first"]).size().reset_index(name="order_count")


def cross_sell_from_chukku(
    seq_df: pd.DataFrame,
    orders_df: pd.DataFrame,
    items_df: pd.DataFrame,
    mix_skus: tuple[str, ...] = ("NSS-400", "MOM-400"),
    min_sample: int = 3,
) -> dict:
    """Of customers whose first order was Chukku Kappi, what share later
    bought one of the ₹999 mixes in a subsequent order?"""
    chukku_customers = set(seq_df.loc[seq_df["first_sku"] == "CK-2PK", "customer_id"])
    cohort_size = len(chukku_customers)
    if cohort_size == 0:
        return {"cohort_size": 0, "converted": 0, "conversion_rate": 0.0, "low_confidence": True}

    orders = orders_df.dropna(subset=["customer_id"])
    first_order_id = orders.sort_values("created_at").groupby("customer_id")["order_id"].first()
    later_orders = orders[
        orders["customer_id"].isin(chukku_customers)
        & (orders["order_id"] != orders["customer_id"].map(first_order_id))
    ]
    later_items = items_df[
        items_df["order_id"].isin(later_orders["order_id"])
        & items_df["product_id"].isin(mix_skus)
        & (items_df["quantity"] > 0)
    ]
    converting_order_ids = set(later_items["order_id"])
    converted_customers = later_orders.loc[
        later_orders["order_id"].isin(converting_order_ids), "customer_id"
    ].unique()

    return {
        "cohort_size": cohort_size,
        "converted": len(converted_customers),
        "conversion_rate": len(converted_customers) / cohort_size,
        "low_confidence": cohort_size < min_sample,
    }
