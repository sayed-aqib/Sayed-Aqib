"""Read-only DataFrame loaders from the DuckDB warehouse.

This is I/O, not a metric — it stays out of backend/metrics so those
functions can remain pure dataframe-in/dataframe-out and unit tested without
a database. Routers/services call these to get input frames, then hand them
to backend/metrics for the actual math.
"""

from __future__ import annotations

from datetime import date

import duckdb
import pandas as pd


def get_shopify_orders_and_items(
    con: duckdb.DuckDBPyConnection, start: date, end: date
) -> tuple[pd.DataFrame, pd.DataFrame]:
    orders = con.execute(
        """
        SELECT order_id, channel, customer_id, created_at, total, discount_amount, financial_status
        FROM orders
        WHERE channel = 'shopify' AND created_at >= ? AND created_at < ?
        """,
        [start, end],
    ).df()

    if orders.empty:
        items = pd.DataFrame(columns=[
            "order_id", "line_seq", "product_id", "raw_sku", "raw_title",
            "quantity", "unit_price", "line_amount", "is_refund_line",
        ])
        return orders, items

    order_ids = list(orders["order_id"])
    placeholders = ", ".join("?" for _ in order_ids)
    items = con.execute(
        f"""
        SELECT order_id, line_seq, product_id, raw_sku, raw_title, quantity,
               unit_price, line_amount, is_refund_line
        FROM order_items
        WHERE order_id IN ({placeholders})
        """,
        order_ids,
    ).df()
    return orders, items


def get_amazon_traffic(con: duckdb.DuckDBPyConnection, start: date, end: date) -> pd.DataFrame:
    return con.execute(
        """
        SELECT date, raw_asin, product_id, sessions, units_ordered, ordered_product_sales
        FROM amazon_product_traffic_daily
        WHERE date >= ? AND date < ?
        """,
        [start, end],
    ).df()


def get_flipkart_traffic(con: duckdb.DuckDBPyConnection, start: date, end: date) -> pd.DataFrame:
    return con.execute(
        """
        SELECT date, raw_fsn, product_id, sessions, units_ordered, ordered_product_sales
        FROM flipkart_product_traffic_daily
        WHERE date >= ? AND date < ?
        """,
        [start, end],
    ).df()


def get_shopify_funnel_daily(con: duckdb.DuckDBPyConnection, start: date, end: date) -> pd.DataFrame:
    return con.execute(
        """
        SELECT date, sessions, added_to_cart, reached_checkout, completed_checkout
        FROM shopify_funnel_daily
        WHERE date >= ? AND date < ?
        """,
        [start, end],
    ).df()


def get_shopify_referrer_sessions(con: duckdb.DuckDBPyConnection, start: date, end: date) -> pd.DataFrame:
    return con.execute(
        "SELECT date, referrer, sessions FROM sessions_daily WHERE date >= ? AND date < ?",
        [start, end],
    ).df()


def get_search_query_weekly(con: duckdb.DuckDBPyConnection, start: date, end: date) -> pd.DataFrame:
    return con.execute(
        """
        SELECT week_start, search_query, impressions, clicks, cart_adds, purchases
        FROM search_query_weekly
        WHERE week_start >= ? AND week_start < ?
        """,
        [start, end],
    ).df()


def get_ad_spend_total(con: duckdb.DuckDBPyConnection, platform: str, start: date, end: date) -> float:
    row = con.execute(
        "SELECT COALESCE(SUM(spend), 0) FROM ad_spend_daily WHERE platform = ? AND date >= ? AND date < ?",
        [platform, start, end],
    ).fetchone()
    return float(row[0])


def get_ad_spend_daily_rows(con: duckdb.DuckDBPyConnection, platform: str, start: date, end: date) -> pd.DataFrame:
    return con.execute(
        """
        SELECT date, campaign_name, adset_name, spend, impressions, clicks,
               purchases, revenue, frequency, new_customers
        FROM ad_spend_daily
        WHERE platform = ? AND date >= ? AND date < ?
        """,
        [platform, start, end],
    ).df()


def get_adset_first_seen(con: duckdb.DuckDBPyConnection, platform: str) -> dict[tuple[str, str], date]:
    rows = con.execute(
        """
        SELECT campaign_name, adset_name, MIN(date) AS first_seen
        FROM ad_spend_daily
        WHERE platform = ?
        GROUP BY campaign_name, adset_name
        """,
        [platform],
    ).fetchall()
    return {(r[0], r[1]): r[2] for r in rows}


def get_products(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return con.execute("SELECT product_id, name, channels, list_price FROM products").df()


def get_warehouse_date_bounds(con: duckdb.DuckDBPyConnection) -> tuple[date | None, date | None]:
    row = con.execute(
        """
        SELECT MIN(d), MAX(d) FROM (
            SELECT CAST(created_at AS DATE) AS d FROM orders
            UNION ALL SELECT date FROM amazon_product_traffic_daily
            UNION ALL SELECT date FROM flipkart_product_traffic_daily
        )
        """
    ).fetchone()
    return row[0], row[1]
