"""Adapter for the Shopify abandoned checkouts export -> ``abandoned_checkouts``."""

from __future__ import annotations

from pathlib import Path

import duckdb

from backend.ingest.common import IngestResult, dedupe_exact_rows, log_issues, read_csv_rows, upsert_rows, validate_rows
from backend.models.parsing import parse_flexible_date
from backend.models.schemas import AbandonedCheckoutRow

SOURCE = "shopify_abandoned_checkouts"
COLUMNS = [
    "checkout_id", "created_at", "email", "phone", "total", "currency",
    "items_in_cart", "recovered", "source_file",
]


def ingest_shopify_abandoned_checkouts(con: duckdb.DuckDBPyConnection, path: Path) -> IngestResult:
    file_label = path.name
    result = IngestResult(source=SOURCE, file=file_label)

    raw_rows = read_csv_rows(path)
    result.rows_read = len(raw_rows)
    deduped, n_dropped = dedupe_exact_rows(raw_rows)
    result.rows_deduped = n_dropped

    valid_rows, issues = validate_rows(deduped, AbandonedCheckoutRow)
    result.issues.extend(issues)
    result.rows_accepted = len(valid_rows)

    tuples = [
        (
            r.checkout_id, parse_flexible_date(r.created_at_raw), r.email or None, r.phone or None,
            r.total, r.currency, r.items_in_cart, r.recovered, file_label,
        )
        for r in valid_rows
    ]
    upsert_rows(con, "abandoned_checkouts", COLUMNS, tuples, ["checkout_id"])
    log_issues(con, SOURCE, file_label, result.issues)
    return result
