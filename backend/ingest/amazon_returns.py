"""Adapter for the Amazon returns export -> ``returns``.

There's no Shopify-side equivalent in the source list: Shopify refunds show
up as negative lines inside the orders export instead (see
backend/ingest/shopify_orders.py).
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from backend.ingest.common import IngestIssue, IngestResult, dedupe_exact_rows, log_issues, read_csv_rows, upsert_rows, validate_rows
from backend.ingest.sku_map import SkuMap
from backend.models.parsing import parse_flexible_date
from backend.models.schemas import AmazonReturnRow

SOURCE = "amazon_returns"
COLUMNS = [
    "return_id", "platform", "return_date", "order_id", "product_id", "raw_sku",
    "reason", "quantity", "refund_amount", "source_file",
]


def ingest_amazon_returns(con: duckdb.DuckDBPyConnection, path: Path, sku_map: SkuMap | None = None) -> IngestResult:
    sku_map = sku_map or SkuMap()
    file_label = path.name
    result = IngestResult(source=SOURCE, file=file_label)

    raw_rows = read_csv_rows(path)
    result.rows_read = len(raw_rows)
    deduped, n_dropped = dedupe_exact_rows(raw_rows)
    result.rows_deduped = n_dropped

    valid_rows, issues = validate_rows(deduped, AmazonReturnRow)
    result.issues.extend(issues)
    result.rows_accepted = len(valid_rows)

    tuples = []
    for r in valid_rows:
        product_id = sku_map.resolve_amazon(r.asin, "") or (r.sku if r.sku in sku_map.product_ids else None)
        if product_id is None:
            result.issues.append(
                IngestIssue(row_number=None, severity="warning", reason=f"unmapped return SKU/ASIN: sku={r.sku!r} asin={r.asin!r}")
            )
        tuples.append((
            f"amazon:{r.order_id}:{r.sku}", "amazon", parse_flexible_date(r.return_date_raw).date(),
            r.order_id, product_id, r.sku or None, r.reason or None, r.quantity,
            r.refund_amount, file_label,
        ))

    upsert_rows(con, "returns", COLUMNS, tuples, ["return_id"])
    log_issues(con, SOURCE, file_label, result.issues)
    return result
