from __future__ import annotations

from datetime import date

import duckdb
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.api.deps import get_db
from backend.api.services import costs_summary, save_cost_version
from backend.metrics.unit_economics import CostVersion

router = APIRouter(prefix="/api/costs", tags=["costs"])


class CostVersionIn(BaseModel):
    effective_date: str
    cogs_per_unit: dict[str, float]
    packaging_per_unit: dict[str, float]
    shipping_shopify_per_order: float
    shopify_gateway_pct: float
    shopify_gateway_fixed: float
    amazon_referral_pct: float
    amazon_fba_per_unit: float
    flipkart_commission_pct: float = 0.0
    flipkart_shipping_per_unit: float = 0.0
    returns_provision_pct: dict[str, float]


@router.get("")
def get_costs(con: duckdb.DuckDBPyConnection = Depends(get_db)) -> dict:
    return costs_summary(con)


@router.post("/versions")
def post_cost_version(body: CostVersionIn, con: duckdb.DuckDBPyConnection = Depends(get_db)) -> dict:
    version = CostVersion(
        effective_date=date.fromisoformat(body.effective_date),
        cogs_per_unit=body.cogs_per_unit,
        packaging_per_unit=body.packaging_per_unit,
        shipping_shopify_per_order=body.shipping_shopify_per_order,
        shopify_gateway_pct=body.shopify_gateway_pct,
        shopify_gateway_fixed=body.shopify_gateway_fixed,
        amazon_referral_pct=body.amazon_referral_pct,
        amazon_fba_per_unit=body.amazon_fba_per_unit,
        flipkart_commission_pct=body.flipkart_commission_pct,
        flipkart_shipping_per_unit=body.flipkart_shipping_per_unit,
        returns_provision_pct=body.returns_provision_pct,
    )
    return save_cost_version(con, version)
