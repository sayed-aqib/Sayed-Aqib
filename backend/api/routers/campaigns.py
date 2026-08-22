from __future__ import annotations

from datetime import date

import duckdb
from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import get_db
from backend.api.services import PLATFORM_CHANNEL, campaign_scoring_summary

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


@router.get("/summary")
def get_campaign_scoring(
    platform: str,
    as_of: date | None = None,
    con: duckdb.DuckDBPyConnection = Depends(get_db),
) -> dict:
    if platform not in PLATFORM_CHANNEL:
        raise HTTPException(status_code=400, detail=f"unknown platform {platform!r}, expected one of {list(PLATFORM_CHANNEL)}")
    return campaign_scoring_summary(con, platform, as_of or date.today())
