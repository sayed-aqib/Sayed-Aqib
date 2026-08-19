"""FastAPI dependency for the shared DuckDB connection.

Single local file, single process (see CLAUDE.md — no auth, runs locally
for v1), so one connection opened at startup and reused is simplest and
avoids DuckDB's single-writer file lock fighting itself across requests.
"""

from __future__ import annotations

import duckdb
from fastapi import Request


def get_db(request: Request) -> duckdb.DuckDBPyConnection:
    return request.app.state.db
