"""Adapter for the Amazon Sponsored Products campaign report -> ``ad_spend_daily``.

Campaign-level rows, so adset_name is left at its table default
'(campaign level)' — Amazon SP reports don't have an adset concept the way
Meta does.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from backend.ingest.common import IngestResult, dedupe_exact_rows, log_issues, read_csv_rows, upsert_rows, validate_rows
from backend.models.parsing import parse_flexible_date
from backend.models.schemas import SpCampaignRow

SOURCE = "amazon_sp_campaign_report"
COLUMNS = [
    "date", "platform", "campaign_name", "adset_name", "impressions", "clicks",
    "spend", "purchases", "revenue", "ctr_pct", "cpc", "cpm", "frequency",
    "reach", "acos_pct", "source_file",
]


def ingest_sp_campaign_report(con: duckdb.DuckDBPyConnection, path: Path) -> IngestResult:
    file_label = path.name
    result = IngestResult(source=SOURCE, file=file_label)

    raw_rows = read_csv_rows(path)
    result.rows_read = len(raw_rows)
    deduped, n_dropped = dedupe_exact_rows(raw_rows)
    result.rows_deduped = n_dropped

    valid_rows, issues = validate_rows(deduped, SpCampaignRow)
    result.issues.extend(issues)
    result.rows_accepted = len(valid_rows)

    tuples = [
        (
            parse_flexible_date(r.date_raw).date(), "amazon", r.campaign_name, "(campaign level)",
            r.impressions, r.clicks, r.spend, r.orders, r.sales, r.ctr, r.cpc,
            None, None, None, r.acos, file_label,
        )
        for r in valid_rows
    ]
    upsert_rows(con, "ad_spend_daily", COLUMNS, tuples, ["date", "platform", "campaign_name", "adset_name"])
    log_issues(con, SOURCE, file_label, result.issues)
    return result
