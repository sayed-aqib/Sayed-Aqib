"""Amazon Search Query Performance -> which keywords need which fix.

A query with plenty of impressions but a poor click rate has a listing or
image problem — shoppers see it and scroll past. A query with a healthy
click rate but a poor purchase rate has a price or review problem — they
click through and still don't buy. These are different fixes, so a query is
classified as one or the other (never both), and "healthy" if it's not
notably worse than its peers on either count.

Thresholds are relative to the query set's own bottom quartile, not a
hardcoded percentage — click-through and conversion rates vary too much by
category for a fixed number to mean anything. The median was tried first
and flagged half of every query set by construction; the bottom quartile
catches queries that are actually lagging their peers, not merely
below-average.
"""

from __future__ import annotations

import pandas as pd


def classify_search_queries(df: pd.DataFrame, min_purchases_confident: int = 3) -> pd.DataFrame:
    grouped = df.groupby("search_query")[["impressions", "clicks", "cart_adds", "purchases"]].sum().reset_index()

    total_impressions = grouped["impressions"].sum()
    total_purchases = grouped["purchases"].sum()

    has_impressions = grouped["impressions"] > 0
    has_clicks = grouped["clicks"] > 0

    grouped["click_rate"] = (grouped["clicks"] / grouped["impressions"]).where(has_impressions, 0.0)
    grouped["purchase_rate"] = (grouped["purchases"] / grouped["clicks"]).where(has_clicks, 0.0)
    grouped["impression_share"] = (grouped["impressions"] / total_impressions) if total_impressions else 0.0
    grouped["conversion_share"] = (grouped["purchases"] / total_purchases) if total_purchases else 0.0

    click_rate_floor = grouped.loc[has_impressions, "click_rate"].quantile(0.25) if has_impressions.any() else 0.0
    purchase_rate_floor = grouped.loc[has_clicks, "purchase_rate"].quantile(0.25) if has_clicks.any() else 0.0

    grouped["issue"] = "healthy"
    is_listing_problem = has_impressions & (grouped["click_rate"] < click_rate_floor)
    grouped.loc[is_listing_problem, "issue"] = "listing_or_image_problem"
    is_price_problem = (
        has_clicks & ~is_listing_problem & (grouped["purchase_rate"] < purchase_rate_floor)
    )
    grouped.loc[is_price_problem, "issue"] = "price_or_review_problem"

    grouped["low_confidence"] = grouped["purchases"] < min_purchases_confident
    return grouped
