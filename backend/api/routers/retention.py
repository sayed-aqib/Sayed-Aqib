from __future__ import annotations

import duckdb
from fastapi import APIRouter, Depends

from backend.api.deps import get_db
from backend.api.services import retention_summary

router = APIRouter(prefix="/api/retention", tags=["retention"])


@router.get("/summary")
def get_summary(con: duckdb.DuckDBPyConnection = Depends(get_db)) -> dict:
    return retention_summary(con)
