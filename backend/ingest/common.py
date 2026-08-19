"""Shared plumbing for adapters: CSV reading, dedup, upsert, issue logging.

Every adapter follows the same shape: read rows → drop exact duplicates →
validate each row against its Pydantic schema (logging rejects) → normalize
→ upsert into DuckDB keyed on a natural key, so re-running the same file
never duplicates rows.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import duckdb
import pydantic


@dataclass
class IngestIssue:
    row_number: int | None
    severity: str  # "rejected" | "warning"
    reason: str
    raw_row: dict[str, Any] | None = None


@dataclass
class IngestResult:
    source: str
    file: str
    rows_read: int = 0
    rows_deduped: int = 0
    rows_accepted: int = 0
    issues: list[IngestIssue] = field(default_factory=list)

    @property
    def rows_rejected(self) -> int:
        return sum(1 for i in self.issues if i.severity == "rejected")

    def summary(self) -> str:
        return (
            f"{self.source} <- {self.file}: read {self.rows_read}, "
            f"deduped {self.rows_deduped}, accepted {self.rows_accepted}, "
            f"rejected {self.rows_rejected}, warnings {len(self.issues) - self.rows_rejected}"
        )


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def dedupe_exact_rows(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], int]:
    """Drop rows that are byte-for-byte identical to an earlier row.

    This is aimed at the "accidentally exported the same row twice" failure
    mode, not at legitimate repeat line items — those differ by at least one
    field (line number, timestamp, etc.) in every real export.
    """
    seen: set[tuple] = set()
    kept: list[dict[str, str]] = []
    n_dropped = 0
    for row in rows:
        key = tuple(row.items())
        if key in seen:
            n_dropped += 1
            continue
        seen.add(key)
        kept.append(row)
    return kept, n_dropped


def validate_rows(
    rows: list[dict[str, str]], schema: type[pydantic.BaseModel]
) -> tuple[list[pydantic.BaseModel], list[IngestIssue]]:
    valid: list[pydantic.BaseModel] = []
    issues: list[IngestIssue] = []
    for i, row in enumerate(rows, start=1):
        try:
            valid.append(schema.model_validate(row))
        except pydantic.ValidationError as e:
            reason = "; ".join(f"{err['loc'][0]}: {err['msg']}" for err in e.errors())
            issues.append(IngestIssue(row_number=i, severity="rejected", reason=reason, raw_row=row))
    return valid, issues


def log_issues(con: duckdb.DuckDBPyConnection, source: str, file: str, issues: list[IngestIssue]) -> None:
    if not issues:
        return
    con.executemany(
        """
        INSERT INTO ingest_issues (source, file, severity, row_number, reason, raw_row)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (source, file, i.severity, i.row_number, i.reason, json.dumps(i.raw_row) if i.raw_row else None)
            for i in issues
        ],
    )


def upsert_rows(
    con: duckdb.DuckDBPyConnection,
    table: str,
    columns: list[str],
    rows: list[tuple],
    conflict_cols: list[str],
) -> None:
    if not rows:
        return
    update_cols = [c for c in columns if c not in conflict_cols]
    placeholders = ", ".join("?" for _ in columns)
    set_clause = ", ".join(f"{c} = excluded.{c}" for c in update_cols)
    sql = (
        f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders}) "
        f"ON CONFLICT ({', '.join(conflict_cols)}) DO UPDATE SET {set_clause}"
    )
    con.executemany(sql, rows)
