"""Runs every adapter against data/raw/<source>/*.csv into the warehouse.

Usage:
    python -m backend.ingest.run_all --db-path data/warehouse.duckdb
"""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb

from backend.ingest import (
    amazon_detail_page_sales_traffic,
    amazon_returns,
    amazon_sp_campaign_report,
    amazon_sp_search_term_report,
    amazon_search_query_performance,
    flipkart_product_traffic,
    flipkart_returns,
    meta_ads_insights,
    shopify_abandoned_checkouts,
    shopify_customers,
    shopify_funnel,
    shopify_orders,
    shopify_sessions,
)
from backend.ingest.common import IngestResult
from backend.ingest.products import seed_products
from backend.ingest.sku_map import SkuMap
from backend.models.ddl import connect

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = REPO_ROOT / "data" / "warehouse.duckdb"
DEFAULT_RAW_DIR = REPO_ROOT / "data" / "raw"


def run_all(con: duckdb.DuckDBPyConnection, raw_dir: Path) -> list[IngestResult]:
    sku_map = SkuMap()
    seed_products(con)

    adapters = {
        "shopify_orders": lambda p: shopify_orders.ingest_shopify_orders(con, p, sku_map),
        "shopify_customers": lambda p: shopify_customers.ingest_shopify_customers(con, p),
        "shopify_sessions_daily": lambda p: shopify_sessions.ingest_shopify_sessions_daily(con, p),
        "shopify_funnel_daily": lambda p: shopify_funnel.ingest_shopify_funnel_daily(con, p),
        "shopify_sessions_referrer": lambda p: shopify_sessions.ingest_shopify_sessions_referrer(con, p),
        "shopify_abandoned_checkouts": lambda p: shopify_abandoned_checkouts.ingest_shopify_abandoned_checkouts(con, p),
        "amazon_detail_page_sales_traffic": lambda p: amazon_detail_page_sales_traffic.ingest_amazon_product_traffic(con, p, sku_map),
        "amazon_search_query_performance": lambda p: amazon_search_query_performance.ingest_search_query_performance(con, p),
        "amazon_sp_campaign_report": lambda p: amazon_sp_campaign_report.ingest_sp_campaign_report(con, p),
        "amazon_sp_search_term_report": lambda p: amazon_sp_search_term_report.ingest_sp_search_term_report(con, p),
        "amazon_returns": lambda p: amazon_returns.ingest_amazon_returns(con, p, sku_map),
        "flipkart_product_traffic": lambda p: flipkart_product_traffic.ingest_flipkart_product_traffic(con, p, sku_map),
        "flipkart_returns": lambda p: flipkart_returns.ingest_flipkart_returns(con, p, sku_map),
        "meta_ads_insights": lambda p: meta_ads_insights.ingest_meta_ads_insights(con, p),
    }

    results: list[IngestResult] = []
    for source, fn in adapters.items():
        source_dir = raw_dir / source
        if not source_dir.exists():
            continue
        for csv_path in sorted(source_dir.glob("*.csv")):
            results.append(fn(csv_path))
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", type=str, default=str(DEFAULT_DB_PATH))
    parser.add_argument("--raw-dir", type=str, default=str(DEFAULT_RAW_DIR))
    args = parser.parse_args()

    Path(args.db_path).parent.mkdir(parents=True, exist_ok=True)
    con = connect(args.db_path)
    try:
        results = run_all(con, Path(args.raw_dir))
    finally:
        con.close()

    if not results:
        print(f"No source files found under {args.raw_dir}. Run backend/synth/generate.py first.")
        return
    for r in results:
        print(r.summary())


if __name__ == "__main__":
    main()
