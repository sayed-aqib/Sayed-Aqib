"""Adapter for Amazon Search Query Performance -> ``search_query_weekly``."""

from __future__ import annotations

from pathlib import Path

import duckdb

from backend.ingest.common import IngestResult, dedupe_exact_rows, log_issues, read_csv_rows, upsert_rows, validate_rows
from backend.models.parsing import parse_flexible_date
from backend.models.schemas import SearchQueryRow

SOURCE = "amazon_search_query_performance"
COLUMNS = [
    "week_start", "search_query", "impressions", "clicks", "click_rate_pct",
    "cart_adds", "purchases", "purchase_rate_pct", "source_file",
]


def ingest_search_query_performance(con: duckdb.DuckDBPyConnection, path: Path) -> IngestResult:
    file_label = path.name
    result = IngestResult(source=SOURCE, file=file_label)

    raw_rows = read_csv_rows(path)
    result.rows_read = len(raw_rows)
    deduped, n_dropped = dedupe_exact_rows(raw_rows)
    result.rows_deduped = n_dropped

    valid_rows, issues = validate_rows(deduped, SearchQueryRow)
    result.issues.extend(issues)
    result.rows_accepted = len(valid_rows)

    tuples = [
        (
            parse_flexible_date(r.week_start_raw).date(), r.search_query, r.impressions, r.clicks,
            r.click_rate_pct, r.cart_adds, r.purchases, r.purchase_rate_pct, file_label,
        )
        for r in valid_rows
    ]
    upsert_rows(con, "search_query_weekly", COLUMNS, tuples, ["week_start", "search_query"])
    log_issues(con, SOURCE, file_label, result.issues)
    return result
