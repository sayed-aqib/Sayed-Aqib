"""Adapters for the two Shopify sessions exports -> ``sessions_daily``.

Both land in the same table: the day-level export writes rows with
referrer='(all)', the referrer-breakdown export writes one row per
referrer per day. The breakdown won't necessarily reconcile exactly to the
(all) total — that's true of Shopify's own multi-touch attribution too, not
a bug in the adapter.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from backend.ingest.common import IngestResult, dedupe_exact_rows, log_issues, read_csv_rows, upsert_rows, validate_rows
from backend.models.parsing import parse_flexible_date
from backend.models.schemas import SessionDailyRow, SessionReferrerRow

DAILY_SOURCE = "shopify_sessions_daily"
REFERRER_SOURCE = "shopify_sessions_referrer"
COLUMNS = ["date", "referrer", "sessions", "source_file"]


def ingest_shopify_sessions_daily(con: duckdb.DuckDBPyConnection, path: Path) -> IngestResult:
    file_label = path.name
    result = IngestResult(source=DAILY_SOURCE, file=file_label)

    raw_rows = read_csv_rows(path)
    result.rows_read = len(raw_rows)
    deduped, n_dropped = dedupe_exact_rows(raw_rows)
    result.rows_deduped = n_dropped

    valid_rows, issues = validate_rows(deduped, SessionDailyRow)
    result.issues.extend(issues)
    result.rows_accepted = len(valid_rows)

    tuples = [
        (parse_flexible_date(r.date_raw).date(), "(all)", r.sessions, file_label)
        for r in valid_rows
    ]
    upsert_rows(con, "sessions_daily", COLUMNS, tuples, ["date", "referrer"])
    log_issues(con, DAILY_SOURCE, file_label, result.issues)
    return result


def ingest_shopify_sessions_referrer(con: duckdb.DuckDBPyConnection, path: Path) -> IngestResult:
    file_label = path.name
    result = IngestResult(source=REFERRER_SOURCE, file=file_label)

    raw_rows = read_csv_rows(path)
    result.rows_read = len(raw_rows)
    deduped, n_dropped = dedupe_exact_rows(raw_rows)
    result.rows_deduped = n_dropped

    valid_rows, issues = validate_rows(deduped, SessionReferrerRow)
    result.issues.extend(issues)
    result.rows_accepted = len(valid_rows)

    tuples = [
        (parse_flexible_date(r.date_raw).date(), r.referrer, r.sessions, file_label)
        for r in valid_rows
    ]
    upsert_rows(con, "sessions_daily", COLUMNS, tuples, ["date", "referrer"])
    log_issues(con, REFERRER_SOURCE, file_label, result.issues)
    return result
