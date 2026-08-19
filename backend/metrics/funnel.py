"""Two funnels, never merged into one number.

Shopify: sessions -> add to cart -> checkout started -> purchase, each step
as a rate of total sessions and a drop-off from the step before. Amazon:
sessions -> unit session % -> units, by child ASIN/product — the only shape
Amazon's own traffic report gives us, so there's no cart/checkout stage to
show for it.
"""

from __future__ import annotations

import pandas as pd


def _safe_div(a: float, b: float) -> float:
    return (a / b) if b else 0.0


def shopify_funnel(df: pd.DataFrame, min_sample: int = 30) -> dict:
    """``df`` is shopify_funnel_daily rows for the window (any grain that
    has sessions/added_to_cart/reached_checkout/completed_checkout columns)."""
    if df.empty:
        sessions = added = checkout = completed = 0
    else:
        sessions = int(df["sessions"].sum())
        added = int(df["added_to_cart"].sum())
        checkout = int(df["reached_checkout"].sum())
        completed = int(df["completed_checkout"].sum())

    added_rate = _safe_div(added, sessions)
    checkout_rate = _safe_div(checkout, sessions)
    completed_rate = _safe_div(completed, sessions)

    return {
        "sessions": sessions,
        "added_to_cart": added,
        "reached_checkout": checkout,
        "completed_checkout": completed,
        "added_to_cart_rate": added_rate,
        "reached_checkout_rate": checkout_rate,
        "completed_checkout_rate": completed_rate,
        "drop_off_sessions_to_cart": 1 - added_rate,
        "drop_off_cart_to_checkout": 1 - _safe_div(checkout, added),
        "drop_off_checkout_to_purchase": 1 - _safe_div(completed, checkout),
        "low_confidence": completed < min_sample,
    }


def shopify_referrer_split(df: pd.DataFrame) -> dict:
    """Paid vs. organic Shopify sessions. ``(all)`` is the day-level total
    row from sessions_daily (see backend/ingest/shopify_sessions.py) and is
    excluded here — it would double count against the per-referrer rows."""
    rows = df[df["referrer"] != "(all)"]
    is_paid = rows["referrer"].str.contains("Ads", case=False, na=False)
    paid = int(rows.loc[is_paid, "sessions"].sum())
    organic = int(rows.loc[~is_paid, "sessions"].sum())
    total = paid + organic
    return {
        "paid_sessions": paid,
        "organic_sessions": organic,
        "paid_share": _safe_div(paid, total),
    }


def amazon_funnel_by_product(df: pd.DataFrame, min_sample: int = 30) -> pd.DataFrame:
    """``df`` is amazon_product_traffic_daily rows. unit_session_pct is
    recomputed from the summed totals, not averaged from daily percentages —
    a day with 2 sessions and 1 unit is not "50% typical", it's noise."""
    grouped = df.groupby("product_id")[["sessions", "units_ordered"]].sum().reset_index()
    grouped["unit_session_pct"] = (grouped["units_ordered"] / grouped["sessions"]).where(
        grouped["sessions"] != 0, 0.0
    )
    grouped["low_confidence"] = grouped["units_ordered"] < min_sample
    return grouped
