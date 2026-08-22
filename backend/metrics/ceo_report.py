"""CEO Report — the founder's first screen. Twelve metrics, each a pure
function over the warehouse DataFrames typed in backend/models/warehouse_schema.py,
returning a uniform MetricResult so every KPI card renders the same way
regardless of what's behind it.

SIGNATURES ONLY at this stage — every function body raises NotImplementedError.
This file is the API contract for review before implementation + the page get
built; see the docstrings for the exact formula and assumption each function
commits to (the same text the frontend's info tooltip will show verbatim).

Design decisions baked into these signatures, flagged for confirmation:

  - Every function takes FULL order/customer history, not a pre-windowed
    slice, because "new customer" and "repeat" both require knowing about
    orders outside the visible period (a customer's first-ever order might
    be a year before the selected range). Windowing happens inside each
    function via `period`/`comparison`. This mirrors how retention.py
    already works, but differs from unit_economics.py, which takes
    pre-filtered frames — flagging the inconsistency rather than hiding it.

  - net_revenue does NOT import unit_economics.shopify_line_economics, even
    though the revenue-side formula overlaps. Reusing it would drag in a
    CostsConfig dependency (it computes full contribution margin, not just
    revenue) for a metric that doesn't need costs. The two are documented
    against the same formula below so they can't silently drift; happy to
    factor a shared `net_revenue_shopify()` helper instead if you'd rather
    not have the formula stated twice.

  - Metrics 2 (growth) and 7 (return rate) each have more than one facet
    (MoM+YoY; value-based+unit-based) that the brief wants shown together on
    one card, so they return a small dict of MetricResult instead of one —
    everything else returns exactly one MetricResult, or one per SKU.

  - `status` distinguishes three real situations a card can be in, so
    "data not connected" is never confused with "genuinely zero":
      "ok"             computed normally (sample_size may still be low)
      "low_confidence" computed, but below the 30-order / 3-conversion bar
                        from CLAUDE.md — value is shown, flagged, not hidden
      "not_connected"  the source table/export doesn't exist yet (this is
                        the only status Inventory Value can have today)
      "not_available"  structurally impossible, not a data gap — e.g. an
                        Amazon-only CAC split, since Amazon shares no
                        customer identity. Never resolves by waiting for
                        more CSVs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal

import pandas as pd

from backend.metrics.unit_economics import CostsConfig

Status = Literal["ok", "low_confidence", "not_connected", "not_available"]


@dataclass
class DateRange:
    start: date  # inclusive
    end: date  # exclusive


@dataclass
class SparklinePoint:
    period: str  # bucket label, e.g. "2026-06-09" (week start) or "2026-06"
    value: float


@dataclass
class MetricResult:
    value: float | None
    comparison_value: float | None
    change_abs: float | None
    change_pct: float | None  # None when comparison_value is 0 or missing — never divide by zero
    status: Status
    sample_size: int | None
    sparkline: list[SparklinePoint] = field(default_factory=list)
    note: str | None = None  # assumption/caveat text the info tooltip surfaces verbatim


# ── Revenue ──────────────────────────────────────────────────────────────


def net_revenue(
    orders: pd.DataFrame,
    order_items: pd.DataFrame,
    amazon_traffic: pd.DataFrame,
    returns: pd.DataFrame,
    period: DateRange,
    comparison: DateRange,
) -> MetricResult:
    """Net Revenue = gross sales − discounts − returns/refunds, EXCLUDING
    tax and shipping (both channels charge/absorb these differently, so
    blending them into "revenue" would make Shopify and Amazon
    incomparable — the assumption the tooltip states verbatim).

    Shopify: sum(order_items.line_amount) over non-refund lines, minus
    order_items refund-line amounts, minus orders.discount_amount
    (allocated the same way unit_economics.shopify_line_economics already
    does — proportional to a line's share of order revenue).

    Amazon: amazon_traffic.ordered_product_sales, minus returns.refund_amount
    for return_date in the period (Amazon returns are reported separately
    from the daily sales aggregate, unlike Shopify's inline refund lines).

    Blended across both channels for this headline card — the existing Unit
    Economics page is where channel-separated numbers live; blending here is
    deliberate for a one-glance executive summary, not a regression of the
    "don't merge Amazon and Shopify" rule elsewhere.
    """
    raise NotImplementedError


def revenue_growth(
    orders: pd.DataFrame,
    order_items: pd.DataFrame,
    amazon_traffic: pd.DataFrame,
    returns: pd.DataFrame,
    period: DateRange,
) -> dict[Literal["mom", "yoy"], MetricResult]:
    """Revenue Growth = (current − prior) / prior, as %. Returns BOTH
    comparisons regardless of whatever comparison period is selected
    elsewhere on the page, because "month over month" and "year over year"
    have fixed meanings and shouldn't move with an unrelated filter:

      mom: period vs. the immediately preceding period of equal length
      yoy: period vs. the same calendar window exactly one year earlier

    Each wraps net_revenue() against its own fixed comparison window.
    yoy.status is "not_connected" (not an error) when the warehouse doesn't
    yet hold 12 months of history — a real state for a 6-month-old brand,
    not a bug.
    """
    raise NotImplementedError


# ── Customers ────────────────────────────────────────────────────────────
# Shopify only, per Order.channel's docstring — every MetricResult below
# carries a note saying so rather than silently underreporting.


def new_customers(orders: pd.DataFrame, period: DateRange, comparison: DateRange) -> MetricResult:
    """New Customers = distinct customer_ids whose first-ever order (across
    ALL history, not just the period) falls within `period`. Requires full
    order history to determine "first-ever," not a windowed slice.
    """
    raise NotImplementedError


def repeat_customer_rate(
    orders: pd.DataFrame, period: DateRange, comparison: DateRange, min_sample: int = 30
) -> MetricResult:
    """Repeat Customer Rate = (customers active in `period` with >1 order in
    their LIFETIME history) / (all distinct customers active in `period`).
    "Active in period" means placed at least one order in the window: this
    is a period-scoped view of an all-time trait, not "ordered twice within
    the period" — a customer who ordered once in January and again in this
    period counts as repeat. low_confidence below 30 customers, per
    CLAUDE.md's own bar.
    """
    raise NotImplementedError


def repeat_product_rate(
    orders: pd.DataFrame, order_items: pd.DataFrame, period: DateRange, comparison: DateRange, min_sample: int = 3
) -> dict[str, MetricResult]:
    """Per SKU (keyed by product_id): of customers who bought THIS SKU at
    least once in `period`, what share have bought it more than once across
    their LIFETIME history (not just within the period)? Answers "does this
    SKU pull in repeat buyers," not "did they rebuy it during this window" —
    flagging this as the one genuinely ambiguous read of the brief's spec;
    the alternative (repeat within the period only) undercounts a SKU
    someone bought in month 1 and rebought in month 4 if the period is only
    month 4. low_confidence below 3 buyers for that SKU in the period.
    """
    raise NotImplementedError


def customer_lifetime_value(
    orders: pd.DataFrame, order_items: pd.DataFrame, period: DateRange, comparison: DateRange, min_sample: int = 30
) -> MetricResult:
    """CLV, evaluated as of period.end (comparison_value as of comparison.end).

    Historical CLV = avg order value × avg orders per customer × avg
    customer lifespan (days between first and last order, averaged only
    over customers with ≥2 orders — a one-order customer has no observed
    lifespan yet). Used only when at least `min_sample` customers have a
    second order; below that, a lifespan average is noise (CLAUDE.md's
    "no models on a small n" concern applies to any average taken over a
    handful of points).

    Fallback = trailing-12-month revenue per customer (sum of order totals
    in the trailing 12 months ÷ distinct customers who ordered in that
    window) when lifespan data is thin. `note` states which formula was
    used — the card must never show a bare number without saying which.
    """
    raise NotImplementedError


# ── Returns ──────────────────────────────────────────────────────────────


def return_refund_rate(
    orders: pd.DataFrame, order_items: pd.DataFrame, returns: pd.DataFrame, period: DateRange, comparison: DateRange
) -> dict[Literal["by_value", "by_units"], MetricResult]:
    """Return / Refund Rate, two views on one card since they can diverge
    (e.g. a few high-value returns move value-rate more than unit-rate):

      by_value: (Shopify refund-line amount + Amazon returns.refund_amount)
                / gross sales (subtotal, pre-discount, pre-tax) in `period`
      by_units: (Shopify refund-line quantity + Amazon returns.quantity)
                / units sold in `period`

    Directional colour is inverted on this card (down is good) — a UI
    concern, noted here since the metric function has no opinion on colour,
    only the sign of change_pct.
    """
    raise NotImplementedError


# ── Marketing ────────────────────────────────────────────────────────────


def total_ad_spend(
    ad_spend_daily: pd.DataFrame, period: DateRange, comparison: DateRange, platform: str | None = None
) -> MetricResult:
    """Total Ad Spend = sum(spend) in `period`, optionally filtered to one
    `platform`; None blends every platform present. Adding a channel later
    (Google, Amazon Ads) is a new value in ad_spend_daily.platform, not a
    signature or schema change — this satisfies the brief's "structure for
    other channels" requirement directly.
    """
    raise NotImplementedError


def cac(
    ad_spend_daily: pd.DataFrame,
    orders: pd.DataFrame,
    period: DateRange,
    comparison: DateRange,
    platform: str | None = None,
) -> MetricResult:
    """CAC = total_ad_spend(period, platform) / new_customers(period).
    Labelled explicitly as BLENDED CAC in `note` — spend isn't attributed to
    the customer who converted, so this is spend-per-new-customer across the
    whole funnel, not a per-channel acquisition cost. Shopify-only
    denominator, same caveat as New Customers.
    """
    raise NotImplementedError


def roas(
    ad_spend_daily: pd.DataFrame, period: DateRange, comparison: DateRange, platform: str | None = None
) -> MetricResult:
    """ROAS = sum(ad_spend_daily.revenue) / sum(ad_spend_daily.spend) in
    `period` — platform-attributed, not Shopify-order revenue. `note`
    explicitly points at the Meta Ads page's blended MER (total Shopify
    revenue ÷ spend) as the more conservative number, since Meta
    over-attributes to itself; this card and that one are intentionally
    different metrics; the note is meant to stop the founder from wondering
    why they disagree.
    """
    raise NotImplementedError


def cost_per_purchase(
    ad_spend_daily: pd.DataFrame, period: DateRange, comparison: DateRange, platform: str | None = None
) -> MetricResult:
    """Cost Per Purchase = spend / sum(ad_spend_daily.purchases) in `period`
    — purchases as the AD PLATFORM counts them. `note` states plainly why
    this differs from CAC: this denominator counts every purchase
    (including repeat buyers and whatever attribution window the platform
    uses), while CAC's denominator is only new customers.
    """
    raise NotImplementedError


# ── Operations ───────────────────────────────────────────────────────────


def inventory_value(
    inventory_snapshots: pd.DataFrame,
    order_items: pd.DataFrame,
    costs: CostsConfig,
    as_of: date,
    low_stock_weeks_threshold: float = 4.0,
) -> dict[str, MetricResult]:
    """Per SKU (keyed by product_id, plus a "total" key summing all SKUs):
    Inventory Value = units_on_hand (latest snapshot at or before `as_of`)
    × cogs_per_unit from CostsConfig.for_date(as_of) — COGS is looked up,
    never duplicated onto the snapshot row (see InventorySnapshot's
    docstring). `note` carries a low-stock flag when weeks_of_cover
    (units_on_hand ÷ avg weekly units sold, trailing 8 weeks of order_items)
    is below `low_stock_weeks_threshold`.

    status="not_connected" for every SKU while inventory_snapshots is empty
    — no inventory export exists yet, so this card is the one place on the
    CEO Report that will show "data not connected" from day one until a
    real stock count arrives.
    """
    raise NotImplementedError
