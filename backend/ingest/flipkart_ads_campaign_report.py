"""Adapter for the Flipkart Ads campaign report -> ``ad_spend_daily``.

Mirrors backend/ingest/amazon_sp_campaign_report.py: campaign-grain rows,
adset_name left at its table default '(campaign level)' since Flipkart Ads
has no adset concept. Sharing the same table (with platform='flipkart') is
what lets the scoring rule engine (backend/metrics/meta_ads.py) score these
campaigns with the exact same functions used for Meta and Amazon SP.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from backend.ingest.common import IngestResult, dedupe_exact_rows, log_issues, read_csv_rows, upsert_rows, validate_rows
from backend.models.parsing import parse_flexible_date
from backend.models.schemas import FlipkartAdsCampaignRow

SOURCE = "flipkart_ads_campaign_report"
COLUMNS = [
    "date", "platform", "campaign_name", "adset_name", "impressions", "clicks",
    "spend", "purchases", "revenue", "ctr_pct", "cpc", "cpm", "frequency",
    "reach", "acos_pct", "new_customers", "source_file",
]


def ingest_flipkart_ads_campaign_report(con: duckdb.DuckDBPyConnection, path: Path) -> IngestResult:
    file_label = path.name
    result = IngestResult(source=SOURCE, file=file_label)

    raw_rows = read_csv_rows(path)
    result.rows_read = len(raw_rows)
    deduped, n_dropped = dedupe_exact_rows(raw_rows)
    result.rows_deduped = n_dropped

    valid_rows, issues = validate_rows(deduped, FlipkartAdsCampaignRow)
    result.issues.extend(issues)
    result.rows_accepted = len(valid_rows)

    tuples = [
        (
            parse_flexible_date(r.date_raw).date(), "flipkart", r.campaign_name, "(campaign level)",
            r.views, r.clicks, r.ad_spend, r.direct_units, r.direct_revenue,
            (r.clicks / r.views * 100) if r.views else 0.0, (r.ad_spend / r.clicks) if r.clicks else None,
            None, None, None, (r.ad_spend / r.direct_revenue * 100) if r.direct_revenue else None, None, file_label,
        )
        for r in valid_rows
    ]
    upsert_rows(con, "ad_spend_daily", COLUMNS, tuples, ["date", "platform", "campaign_name", "adset_name"])
    log_issues(con, SOURCE, file_label, result.issues)
    return result
