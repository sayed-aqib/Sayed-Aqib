"""FastAPI dependency for the DuckDB connection.

Single local file, single process (see CLAUDE.md — no auth, runs locally
for v1), so one connection is opened at startup and reused. But FastAPI
runs sync endpoints in a threadpool, and a single DuckDBPyConnection isn't
safe to query concurrently from multiple threads — a page like Overview
that fires several requests in parallel would intermittently corrupt
results. ``con.cursor()`` hands each request its own handle onto the same
in-process database, which is safe.
"""

from __future__ import annotations

import duckdb
from fastapi import Request


def get_db(request: Request) -> duckdb.DuckDBPyConnection:
    return request.app.state.db.cursor()
