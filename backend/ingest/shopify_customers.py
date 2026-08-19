"""Adapter for the Shopify customers export -> ``customers``.

Keyed by lowercased email rather than Shopify's numeric Id, because that's
the only field the orders export and the customers export share.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from backend.ingest.common import (
    IngestResult,
    dedupe_exact_rows,
    log_issues,
    read_csv_rows,
    upsert_rows,
    validate_rows,
)
from backend.models.schemas import ShopifyCustomerRow

SOURCE = "shopify_customers"

COLUMNS = [
    "customer_id", "channel", "shopify_numeric_id", "email", "first_name", "last_name",
    "phone", "city", "province", "country", "accepts_marketing", "total_spent",
    "total_orders", "source_file",
]


def ingest_shopify_customers(con: duckdb.DuckDBPyConnection, path: Path) -> IngestResult:
    file_label = path.name
    result = IngestResult(source=SOURCE, file=file_label)

    raw_rows = read_csv_rows(path)
    result.rows_read = len(raw_rows)
    deduped, n_dropped = dedupe_exact_rows(raw_rows)
    result.rows_deduped = n_dropped

    valid_rows, issues = validate_rows(deduped, ShopifyCustomerRow)
    result.issues.extend(issues)
    result.rows_accepted = len(valid_rows)

    tuples = [
        (
            f"shopify:{r.email.lower()}", "shopify", r.id, r.email, r.first_name, r.last_name,
            r.phone or None, r.city or None, r.province or None, r.country or None,
            r.accepts_marketing, r.total_spent, r.total_orders, file_label,
        )
        for r in valid_rows
        if r.email
    ]
    upsert_rows(con, "customers", COLUMNS, tuples, ["customer_id"])
    log_issues(con, SOURCE, file_label, result.issues)
    return result
