"""Adapter for Amazon Detail Page Sales & Traffic by Child Item -> ``amazon_product_traffic_daily``.

This is Amazon's aggregate day/ASIN report — there's no order- or
customer-level data in it (Amazon doesn't share that with sellers), which is
why the Amazon funnel and revenue in Step 2/3 run off this table instead of
an ``orders`` row per purchase.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from backend.ingest.common import IngestIssue, IngestResult, dedupe_exact_rows, log_issues, read_csv_rows, upsert_rows, validate_rows
from backend.ingest.sku_map import SkuMap
from backend.models.parsing import parse_flexible_date
from backend.models.schemas import AmazonProductTrafficRow

SOURCE = "amazon_detail_page_sales_traffic"
COLUMNS = [
    "date", "raw_asin", "product_id", "sessions", "page_views", "buybox_pct",
    "units_ordered", "unit_session_pct", "ordered_product_sales", "source_file",
]


def ingest_amazon_product_traffic(con: duckdb.DuckDBPyConnection, path: Path, sku_map: SkuMap | None = None) -> IngestResult:
    sku_map = sku_map or SkuMap()
    file_label = path.name
    result = IngestResult(source=SOURCE, file=file_label)

    raw_rows = read_csv_rows(path)
    result.rows_read = len(raw_rows)
    deduped, n_dropped = dedupe_exact_rows(raw_rows)
    result.rows_deduped = n_dropped

    valid_rows, issues = validate_rows(deduped, AmazonProductTrafficRow)
    result.issues.extend(issues)
    result.rows_accepted = len(valid_rows)

    tuples = []
    for r in valid_rows:
        product_id = sku_map.resolve_amazon(r.asin, r.title)
        if product_id is None:
            result.issues.append(
                IngestIssue(row_number=None, severity="warning", reason=f"unmapped ASIN: {r.asin!r} title={r.title!r}")
            )
        tuples.append((
            parse_flexible_date(r.date_raw).date(), r.asin, product_id, r.sessions, r.page_views,
            r.buybox_pct, r.units_ordered, r.unit_session_pct, r.ordered_product_sales, file_label,
        ))

    upsert_rows(con, "amazon_product_traffic_daily", COLUMNS, tuples, ["date", "raw_asin"])
    log_issues(con, SOURCE, file_label, result.issues)
    return result
