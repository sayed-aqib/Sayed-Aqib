"""Adapter for Flipkart's sales/traffic report -> ``flipkart_product_traffic_daily``.

Mirrors backend/ingest/amazon_detail_page_sales_traffic.py: Flipkart's Seller
Hub gives sellers a daily/FSN aggregate, not order- or customer-level data,
so Flipkart revenue and funnel run off this table the same way Amazon's does
off amazon_product_traffic_daily.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from backend.ingest.common import IngestIssue, IngestResult, dedupe_exact_rows, log_issues, read_csv_rows, upsert_rows, validate_rows
from backend.ingest.sku_map import SkuMap
from backend.models.parsing import parse_flexible_date
from backend.models.schemas import FlipkartProductTrafficRow

SOURCE = "flipkart_product_traffic"
COLUMNS = ["date", "raw_fsn", "product_id", "sessions", "units_ordered", "ordered_product_sales", "source_file"]


def ingest_flipkart_product_traffic(con: duckdb.DuckDBPyConnection, path: Path, sku_map: SkuMap | None = None) -> IngestResult:
    sku_map = sku_map or SkuMap()
    file_label = path.name
    result = IngestResult(source=SOURCE, file=file_label)

    raw_rows = read_csv_rows(path)
    result.rows_read = len(raw_rows)
    deduped, n_dropped = dedupe_exact_rows(raw_rows)
    result.rows_deduped = n_dropped

    valid_rows, issues = validate_rows(deduped, FlipkartProductTrafficRow)
    result.issues.extend(issues)
    result.rows_accepted = len(valid_rows)

    tuples = []
    for r in valid_rows:
        product_id = sku_map.resolve_flipkart(r.fsn, r.title)
        if product_id is None:
            result.issues.append(
                IngestIssue(row_number=None, severity="warning", reason=f"unmapped FSN: {r.fsn!r} title={r.title!r}")
            )
        tuples.append((
            parse_flexible_date(r.date_raw).date(), r.fsn, product_id, r.sessions,
            r.units_ordered, r.ordered_product_sales, file_label,
        ))

    upsert_rows(con, "flipkart_product_traffic_daily", COLUMNS, tuples, ["date", "raw_fsn"])
    log_issues(con, SOURCE, file_label, result.issues)
    return result
