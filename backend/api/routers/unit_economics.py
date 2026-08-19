from __future__ import annotations

from datetime import date, timedelta

import duckdb
from fastapi import APIRouter, Depends

from backend.api import repo
from backend.api.deps import get_db
from backend.api.services import unit_economics_summary

router = APIRouter(prefix="/api/unit-economics", tags=["unit-economics"])


@router.get("/summary")
def get_summary(
    start: date | None = None,
    end: date | None = None,
    con: duckdb.DuckDBPyConnection = Depends(get_db),
) -> dict:
    if start is None or end is None:
        min_d, max_d = repo.get_warehouse_date_bounds(con)
        start = start or min_d or date.today() - timedelta(days=90)
        end = end or (max_d + timedelta(days=1) if max_d else date.today())
    return unit_economics_summary(con, start, end)
