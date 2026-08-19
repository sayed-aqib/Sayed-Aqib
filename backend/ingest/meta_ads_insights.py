"""Adapter for the Meta Ads insights export (campaign/adset/day) -> ``ad_spend_daily``."""

from __future__ import annotations

from pathlib import Path

import duckdb

from backend.ingest.common import IngestResult, dedupe_exact_rows, log_issues, read_csv_rows, upsert_rows, validate_rows
from backend.models.parsing import parse_flexible_date
from backend.models.schemas import MetaAdsRow

SOURCE = "meta_ads_insights"
COLUMNS = [
    "date", "platform", "campaign_name", "adset_name", "impressions", "clicks",
    "spend", "purchases", "revenue", "ctr_pct", "cpc", "cpm", "frequency",
    "reach", "acos_pct", "new_customers", "source_file",
]


def ingest_meta_ads_insights(con: duckdb.DuckDBPyConnection, path: Path) -> IngestResult:
    file_label = path.name
    result = IngestResult(source=SOURCE, file=file_label)

    raw_rows = read_csv_rows(path)
    result.rows_read = len(raw_rows)
    deduped, n_dropped = dedupe_exact_rows(raw_rows)
    result.rows_deduped = n_dropped

    valid_rows, issues = validate_rows(deduped, MetaAdsRow)
    result.issues.extend(issues)
    result.rows_accepted = len(valid_rows)

    tuples = [
        (
            parse_flexible_date(r.date_raw).date(), "meta", r.campaign_name, r.adset_name,
            r.impressions, r.clicks, r.spend, r.purchases, r.revenue, r.ctr_pct,
            (r.spend / r.clicks) if r.clicks else None, r.cpm, r.frequency, r.reach, None,
            r.new_customers, file_label,
        )
        for r in valid_rows
    ]
    upsert_rows(con, "ad_spend_daily", COLUMNS, tuples, ["date", "platform", "campaign_name", "adset_name"])
    log_issues(con, SOURCE, file_label, result.issues)
    return result
