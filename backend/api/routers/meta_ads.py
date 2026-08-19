from __future__ import annotations

from datetime import date, timedelta

import duckdb
from fastapi import APIRouter, Depends

from backend.api import repo
from backend.api.deps import get_db
from backend.api.services import meta_ads_summary

router = APIRouter(prefix="/api/meta-ads", tags=["meta-ads"])


@router.get("/summary")
def get_summary(
    as_of: date | None = None,
    con: duckdb.DuckDBPyConnection = Depends(get_db),
) -> dict:
    if as_of is None:
        _, max_d = repo.get_warehouse_date_bounds(con)
        as_of = max_d + timedelta(days=1) if max_d else date.today()
    return meta_ads_summary(con, as_of)
