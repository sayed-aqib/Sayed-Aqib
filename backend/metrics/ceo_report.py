"""CEO Report — the founder's first screen. Twelve metrics, each a pure
function over the warehouse DataFrames typed in backend/models/warehouse_schema.py,
returning a uniform MetricResult so every KPI card renders the same way
regardless of what's behind it.

SIGNATURES ONLY at this stage — every function body raises NotImplementedError.
This is the API contract for review before ANY implementation; after
approval, only three are being built end to end first — net_revenue,
new_customers, total_ad_spend, including the date-range filter and
comparison-period logic — the other nine stay signatures until that's done.

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

  - `status` distinguishes FOUR real situations a card can be in, so
    "data not connected" is never confused with "genuinely zero" and a
    permanent structural gap is never confused with a temporary one:
      "ok"             computed normally (sample_size may still be low)
      "low_confidence" computed, but below the 30-order / 3-conversion bar
                        from CLAUDE.md — value is shown, flagged, not hidden
      "not_connected"  the source table/export doesn't exist yet but
                        plausibly will (e.g. Inventory Value, until a stock
                        count CSV arrives) — a temporary gap
      "not_available"  structurally impossible, not a data gap — e.g.
                        Amazon/Flipkart customer identity, which neither
                        marketplace gives sellers. Does NOT resolve by
                        waiting for more CSVs; see the note on Order in
                        backend/models/warehouse_schema.py.

  - Two things this contract deliberately does NOT decide (per instruction —
    both stay open, structured so either answer works later):

      1. ROAS source. AdSpendDaily.revenue (platform/self-attributed) and
         Order.attributed_campaign (order-level attribution — a proposed,
         not-yet-live field) are both in the schema. roas() below takes a
         REQUIRED `source` argument rather than defaulting to one, so the
         choice has to be made explicitly by whoever calls it, not buried
         in the metric.

      2. Customer identity across Amazon/Flipkart. Assumed here that an
         email or stable buyer id may never arrive for either marketplace
         (see Order's docstring in warehouse_schema.py) — every metric that
         touches customer identity (3, 4, 5, 6, 9) is scoped to Shopify
         only and documents that this is a ceiling, not a gap: Repeat
         Customer Rate and CLV will structurally understate true
         cross-channel/Amazon-repeat behavior forever, not just "until more
         data arrives." That's a real limitation worth the founder seeing
         stated plainly on the card, not softened.
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
    flag: Literal["low_stock"] | None = None  # a business-rule flag distinct from status/confidence; today only Inventory Value sets this


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
    "don't merge Amazon and Shopify" rule elsewhere. Flipkart is left out of
    this first build (only Shopify + Amazon are in scope for the 3 metrics
    being built now) and would be the next line added, same shape as Amazon.

    sample_size: Shopify order count + Amazon units sold in `period` — the
    same low_confidence bar (30) used across the rest of CLAUDE.md.
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
# Shopify only, per Order.channel's docstring — and, per the open decision
# on customer identity, presumed to STAY Shopify only. Every MetricResult
# below carries a note saying so; status is "not_available" (not
# "not_connected") wherever the absence is structural rather than temporary.


def new_customers(orders: pd.DataFrame, period: DateRange, comparison: DateRange) -> MetricResult:
    """New Customers = distinct customer_ids whose first-ever order (across
    ALL history, not just the period) falls within `period`. Requires full
    order history to determine "first-ever," not a windowed slice.

    Shopify-only by construction (Amazon/Flipkart rows have no customer_id).
    That's not a partial view pending more data — see warehouse_schema.py's
    note on Order.channel — so this is reported as "New Shopify Customers"
    on the card, not "New Customers" unqualified.
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

    Shopify-only, and structurally so (see new_customers above): a customer
    who buys once on Shopify and repeatedly on Amazon reads as "not repeat"
    here, permanently. The card states this is a floor, not the true rate.
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

    Shopify-only, same structural ceiling as new_customers/repeat_customer_rate.
    """
    raise NotImplementedError


def customer_lifetime_value(
    orders: pd.DataFrame, order_items: pd.DataFrame, period: DateRange, comparison: DateRange, min_sample: int = 30
) -> MetricResult:
    """CLV, evaluated as of period.end (comparison_value as of comparison.end).

    Historical CLV = avg order value × avg orders-per-customer-per-year ×
    avg customer lifespan in years (both averaged only over customers with
    ≥2 orders — a one-order customer has no observed lifespan or repeat
    rate yet). Used only when at least `min_sample` such customers exist;
    below that, an average taken over a handful of points is noise
    (CLAUDE.md's "no models on a small n" concern applies to any average,
    not just a fitted model).

    Fallback = trailing-12-month revenue per customer (sum of order totals
    in the trailing 12 months ÷ distinct customers who ordered in that
    window) when lifespan data is thin. `note` states which formula was
    used — the card must never show a bare number without saying which.

    Shopify-only, and — per the open decision on customer identity —
    presumed permanently so: this is "Shopify CLV," and is expected to
    understate true lifetime value for any customer who also buys on
    Amazon or Flipkart. The card says so; it is not expected to resolve.
    """
    raise NotImplementedError


# ── Returns ──────────────────────────────────────────────────────────────


def return_refund_rate(
    orders: pd.DataFrame,
    order_items: pd.DataFrame,
    amazon_traffic: pd.DataFrame,
    returns: pd.DataFrame,
    period: DateRange,
    comparison: DateRange,
) -> dict[Literal["by_value", "by_units"], MetricResult]:
    """Return / Refund Rate, two views on one card since they can diverge
    (e.g. a few high-value returns move value-rate more than unit-rate):

      by_value: (Shopify refund-line amount + Amazon returns.refund_amount)
                / gross sales (Shopify subtotal, pre-discount, pre-tax, +
                Amazon ordered_product_sales) in `period`
      by_units: (Shopify refund-line quantity + Amazon returns.quantity)
                / units sold (Shopify + Amazon) in `period`

    NOTE: takes `amazon_traffic` — absent from the first draft of this
    signature, which would have computed a *rate* against a *Shopify-only*
    denominator while blending Amazon's refund value into the numerator.
    Caught while reviewing this contract, not after implementing it.

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
    denominator, same structural ceiling as New Customers.
    """
    raise NotImplementedError


def roas(
    ad_spend_daily: pd.DataFrame,
    orders: pd.DataFrame,
    period: DateRange,
    comparison: DateRange,
    source: Literal["platform_attributed", "order_attributed"],
    platform: str | None = None,
) -> MetricResult:
    """ROAS = revenue ÷ ad_spend_daily.spend in `period`, where "revenue"
    means one of two genuinely different things depending on `source` —
    OPEN DECISION 1, not resolved here, which is why `source` has no
    default and must be passed explicitly:

      "platform_attributed": sum(ad_spend_daily.revenue) — what the
        platform itself claims. Over-attributes to varying degrees; see
        the Ad Campaigns page's blended MER for the coarser corrective
        already built for Meta/Amazon SP/Flipkart Ads.

      "order_attributed": sum(orders.total) where orders.attributed_campaign
        matches spend in the same window — a finer, seller-side number,
        but only as good as whatever populates attributed_campaign (a
        field proposed, not live, in warehouse_schema.py), and simply
        wrong at the sub-campaign windowing (attribution lag/last-touch
        assumptions) — no better or worse than the platform's own claim,
        just differently wrong. `note` says which source was used.
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
    orders: pd.DataFrame,
    order_items: pd.DataFrame,
    costs: CostsConfig,
    as_of: date,
    low_stock_weeks_threshold: float = 4.0,
) -> dict[str, MetricResult]:
    """Per SKU (keyed by product_id, plus a "total" key summing all SKUs):
    Inventory Value = units_on_hand (latest snapshot at or before `as_of`)
    × cogs_per_unit from CostsConfig.for_date(as_of) — COGS is looked up,
    never duplicated onto the snapshot row (see InventorySnapshot's
    docstring). `flag="low_stock"` when weeks_of_cover (units_on_hand ÷ avg
    weekly units sold, trailing 8 weeks of order_items joined to orders for
    a date) is below `low_stock_weeks_threshold`.

    NOTE: takes `orders` in addition to `order_items` — absent from the
    first draft, which had no date to compute a trailing sales-velocity
    window from (order_items alone has no date column). Same category of
    fix as return_refund_rate above.

    status="not_connected" for every SKU while inventory_snapshots is empty
    — no inventory export exists yet, so this card is the one place on the
    CEO Report that will show "data not connected" from day one (a
    temporary gap, unlike the customer-identity ceiling above) until a real
    stock count arrives.
    """
    raise NotImplementedError
