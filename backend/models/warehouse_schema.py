"""Typed contract for the normalized warehouse rows the CEO Report reads.

This documents DataFrame shape, not a new source of truth. Five of these six
TypedDicts mirror an existing DuckDB table column-for-column (see
backend/models/ddl.py and backend/api/repo.py) — nothing here renames or
reinterprets a field that's already live. Only ``InventorySnapshot`` is new:
no inventory export has arrived yet, so there's no table for it (see the
note on that class for why unit_cost isn't stored on it). No DDL change is
proposed here yet — inventory_snapshots stays a documented proposal, not a
live table, until this contract is reviewed.

Every backend/metrics/ceo_report.py function is written against these types,
not against a live DuckDB connection — the same "pure function over a
DataFrame, no I/O" rule the rest of backend/metrics follows. Swapping mock
data for the real warehouse later means pointing the data-source adapter
(backend/api/repo.py) at real tables; the metric functions don't change.

TWO OPEN DECISIONS — deliberately not resolved by this contract, structured
so either answer is possible later without a schema change:

1. ROAS source (Meta/platform-attributed vs. our own order-level
   attribution). AdSpendDaily.revenue is explicitly ONE candidate (what the
   platform self-reports); Order.attributed_campaign is the other (whichever
   order actually converted, joined to campaign spend). Both fields exist
   side by side; nothing here picks a winner.

2. Customer identity across Amazon (and, on the same reasoning, Flipkart).
   Order.customer_id is null for both today, and — per the assumption
   flagged on that field below — may permanently stay null: marketplace
   sellers generally aren't given a buyer's email or a stable cross-order
   identity. If that holds, New Customers/Repeat Customer Rate/Repeat
   Product Rate/CLV are not just "Shopify-only for now" but "Shopify-only,
   full stop" — see the status semantics note on each affected metric in
   backend/metrics/ceo_report.py. That's a real ceiling on those four
   numbers, not a data-completeness gap that a future CSV fixes.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TypedDict


class Order(TypedDict):
    order_id: str
    channel: str
    """'shopify' | 'amazon' | 'flipkart'. Amazon and Flipkart rows exist for
    revenue reconciliation only — neither marketplace's seller-facing report
    includes a buyer email or a stable cross-order buyer id, so customer_id
    is null on those rows (see Customer below) and there is currently no
    known path to change that. Treat this as a permanent structural limit,
    not a "waiting on a better export" gap: every customer-identity metric
    (New Customers, Repeat Customer Rate, Repeat Product Rate, CLV) is
    Shopify-only and is expected to STAY Shopify-only."""
    customer_id: str | None
    created_at: datetime
    subtotal: float
    shipping: float
    taxes: float
    discount_amount: float
    total: float
    refunded_amount: float
    financial_status: str
    attributed_campaign: str | None
    """NOT a live column yet — proposed alongside this contract as the
    order-level ROAS attribution path (open decision 1 above). Whatever
    mechanism ends up populating it (a captured UTM campaign, a
    campaign-specific discount code, or manual tagging) is undecided; the
    field exists so "revenue attributed by matching an order back to the
    campaign that drove it" is structurally possible side by side with
    AdSpendDaily.revenue's platform-self-reported number, without deciding
    between them now."""


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
    """'meta' | 'amazon' | 'flipkart' today. Every ceo_report ad-spend
    function groups or filters on this column rather than assuming one
    platform, so a new platform is a new value here, not a schema or
    function-signature change — this is what satisfies requirement 8's
    "structure for other channels"."""
    campaign_name: str
    adset_name: str
    spend: float
    purchases: int
    """Platform-attributed purchases — counts repeat buyers and is subject
    to the platform's own attribution window, which is why Cost Per
    Purchase (11) and CAC (9) are deliberately different metrics."""
    revenue: float
    """Platform-attributed (self-reported) revenue — ONE of the two
    candidate ROAS (10) numerators, not the only one (open decision 1
    above). Meta/Amazon/Flipkart all over-attribute this to themselves to
    varying degrees relative to what a seller's own order data shows; see
    the Ad Campaigns page's "blended MER" for the coarse channel-level
    corrective already built. Order.attributed_campaign is the other
    candidate — a finer, order-level alternative. roas() takes an explicit
    ``source`` argument rather than defaulting to one."""
    new_customers: int


class InventorySnapshot(TypedDict):
    """NEW — no table or ingest adapter exists yet; this is a proposal.
    Point-in-time stock count only. unit_cost is deliberately NOT a field
    here: Inventory Value (12) looks COGS up from config/costs.yaml via the
    existing effective-dated CostsConfig, so stock valuation and product
    cost never have two places to go out of sync. Until a real export
    lands, every Inventory Value card reads status="not_connected" — this
    one, unlike the customer-identity gap above, genuinely is just waiting
    on a CSV, not a structural ceiling."""

    product_id: str
    snapshot_date: date
    units_on_hand: int
