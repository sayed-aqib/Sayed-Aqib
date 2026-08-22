"""Typed contract for the normalized warehouse rows the CEO Report reads.

This documents DataFrame shape, not a new source of truth. Five of these six
TypedDicts mirror an existing DuckDB table column-for-column (see
backend/models/ddl.py and backend/api/repo.py) — nothing here renames or
reinterprets a field that's already live. Only ``InventorySnapshot`` is new:
no inventory export has arrived yet, so there's no table for it (see the
note on that class for why unit_cost isn't stored on it).

Every backend/metrics/ceo_report.py function is written against these types,
not against a live DuckDB connection — the same "pure function over a
DataFrame, no I/O" rule the rest of backend/metrics follows. Swapping mock
data for the real warehouse later means pointing the data-source adapter
(backend/api/repo.py) at real tables; the metric functions don't change.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TypedDict


class Order(TypedDict):
    order_id: str
    channel: str
    """'shopify' | 'amazon'. Amazon rows exist for revenue reconciliation
    only — Amazon's Detail Page Sales & Traffic report never gives sellers
    an order-level or customer-level identity, so an Amazon row's
    customer_id is always null (see Customer below). Every customer-based
    metric (New Customers, Repeat rates, CLV) is Shopify-only for that
    reason, same as the existing Retention page."""
    customer_id: str | None
    created_at: datetime
    subtotal: float
    shipping: float
    taxes: float
    discount_amount: float
    total: float
    refunded_amount: float
    financial_status: str


class OrderItem(TypedDict):
    order_id: str
    line_seq: int
    product_id: str | None
    """None when the raw SKU/title didn't resolve via config/sku_map.yaml —
    excluded from per-SKU metrics (5, 12) but still counted in blended ones."""
    quantity: int
    unit_price: float
    line_amount: float
    is_refund_line: bool


class Customer(TypedDict):
    customer_id: str
    channel: str
    email: str | None
    total_spent: float
    total_orders: int


class Product(TypedDict):
    product_id: str
    name: str
    channels: str
    """Comma list, e.g. "shopify,amazon" — matches products.yaml verbatim."""
    list_price: float


class AdSpendDaily(TypedDict):
    date: date
    platform: str
    """'meta' today. Every ceo_report ad-spend function groups or filters on
    this column rather than assuming Meta, so a Google/Amazon-Ads adapter
    can add rows here later with no schema or function-signature change —
    this is what satisfies requirement 8's "structure for other channels"."""
    campaign_name: str
    adset_name: str
    spend: float
    purchases: int
    """Platform-attributed purchases — counts repeat buyers and is subject
    to the platform's own attribution window, which is why Cost Per
    Purchase (11) and CAC (9) are deliberately different metrics."""
    revenue: float
    """Platform-attributed revenue, used for ROAS (10). Meta over-attributes
    this relative to Shopify's own order data — see the existing Meta Ads
    page's "blended MER" for the more conservative number; the CEO Report's
    ROAS tooltip cross-references it rather than silently disagreeing."""
    new_customers: int


class InventorySnapshot(TypedDict):
    """NEW — no table or ingest adapter exists yet; this is a proposal.
    Point-in-time stock count only. unit_cost is deliberately NOT a field
    here: Inventory Value (12) looks COGS up from config/costs.yaml via the
    existing effective-dated CostsConfig, so stock valuation and product
    cost never have two places to go out of sync. Until a real export
    lands, every Inventory Value card reads status="not_connected"."""

    product_id: str
    snapshot_date: date
    units_on_hand: int
