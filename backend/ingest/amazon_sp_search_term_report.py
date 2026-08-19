"""Adapter for the Amazon Sponsored Products search term report -> ``ad_search_terms_weekly``.

Kept separate from ``search_query_weekly`` (organic Search Query
Performance) — one is paid spend by term, the other is organic
impression/conversion share. Mixing them would hide which lever (bid vs.
listing) actually needs pulling.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from backend.ingest.common import IngestResult, dedupe_exact_rows, log_issues, read_csv_rows, upsert_rows, validate_rows
from backend.models.parsing import parse_flexible_date
from backend.models.schemas import SpSearchTermRow

SOURCE = "amazon_sp_search_term_report"
COLUMNS = [
    "week_start", "platform", "campaign_name", "ad_group_name", "match_type",
    "search_term", "impressions", "clicks", "spend", "sales", "orders", "source_file",
]


def ingest_sp_search_term_report(con: duckdb.DuckDBPyConnection, path: Path) -> IngestResult:
    file_label = path.name
    result = IngestResult(source=SOURCE, file=file_label)

    raw_rows = read_csv_rows(path)
    result.rows_read = len(raw_rows)
    deduped, n_dropped = dedupe_exact_rows(raw_rows)
    result.rows_deduped = n_dropped

    valid_rows, issues = validate_rows(deduped, SpSearchTermRow)
    result.issues.extend(issues)
    result.rows_accepted = len(valid_rows)

    tuples = [
        (
            parse_flexible_date(r.date_raw).date(), "amazon", r.campaign_name, r.ad_group_name,
            r.match_type or None, r.search_term, r.impressions, r.clicks, r.spend,
            r.sales_7d, r.orders_7d, file_label,
        )
        for r in valid_rows
    ]
    upsert_rows(
        con, "ad_search_terms_weekly", COLUMNS, tuples,
        ["week_start", "campaign_name", "ad_group_name", "search_term"],
    )
    log_issues(con, SOURCE, file_label, result.issues)
    return result
