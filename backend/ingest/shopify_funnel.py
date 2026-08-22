"""Adapter for Shopify's own funnel report -> ``shopify_funnel_daily``.

sessions -> added to cart -> reached checkout -> completed checkout. Kept
separate from ``abandoned_checkouts`` (which is individual carts, useful for
recovery outreach) — this is the aggregate daily counts the Funnel screen's
drop-off percentages are computed from.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from backend.ingest.common import IngestResult, dedupe_exact_rows, log_issues, read_csv_rows, upsert_rows, validate_rows
from backend.models.parsing import parse_flexible_date
from backend.models.schemas import ShopifyFunnelDailyRow

SOURCE = "shopify_funnel_daily"
COLUMNS = [
    "date", "sessions", "home_page_views", "product_page_views",
    "added_to_cart", "reached_checkout", "completed_checkout", "source_file",
]


def ingest_shopify_funnel_daily(con: duckdb.DuckDBPyConnection, path: Path) -> IngestResult:
    file_label = path.name
    result = IngestResult(source=SOURCE, file=file_label)

    raw_rows = read_csv_rows(path)
    result.rows_read = len(raw_rows)
    deduped, n_dropped = dedupe_exact_rows(raw_rows)
    result.rows_deduped = n_dropped

    valid_rows, issues = validate_rows(deduped, ShopifyFunnelDailyRow)
    result.issues.extend(issues)
    result.rows_accepted = len(valid_rows)

    tuples = [
        (
            parse_flexible_date(r.date_raw).date(), r.sessions, r.home_page_views, r.product_page_views,
            r.added_to_cart, r.reached_checkout, r.completed_checkout, file_label,
        )
        for r in valid_rows
    ]
    upsert_rows(con, "shopify_funnel_daily", COLUMNS, tuples, ["date"])
    log_issues(con, SOURCE, file_label, result.issues)
    return result
