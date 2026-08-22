"""Contribution margin — the headline module.

    contribution margin = net revenue − COGS − packaging − shipping borne by
    the brand − channel fees − returns provision − allocated ad spend

Shopify has real per-order data, so its economics run at line-item grain and
roll up to orders. Amazon's only revenue source we have (Detail Page Sales &
Traffic) is a daily aggregate by ASIN — Amazon doesn't hand sellers
order-level or customer-level data — so Amazon economics run at
(date, product_id) grain instead. The two channels are never merged into one
row; ``channel_summary`` puts them side by side.

Every cost comes from config/costs.yaml, resolved per row using the cost
version effective on *that row's own date* (CostsConfig.for_date), so
editing the config for a price change never rewrites history.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd
import yaml


@dataclass
class CostVersion:
    effective_date: date
    cogs_per_unit: dict[str, float]
    packaging_per_unit: dict[str, float]
    shipping_shopify_per_order: float
    shopify_gateway_pct: float
    shopify_gateway_fixed: float
    amazon_referral_pct: float
    amazon_fba_per_unit: float
    returns_provision_pct: dict[str, float]
    flipkart_commission_pct: float = 0.0
    flipkart_shipping_per_unit: float = 0.0


@dataclass
class CostsConfig:
    versions: list[CostVersion]

    def for_date(self, d: date) -> CostVersion:
        applicable = [v for v in self.versions if v.effective_date <= d]
        if not applicable:
            raise ValueError(f"no cost config version effective on or before {d}")
        return max(applicable, key=lambda v: v.effective_date)


def _as_date(v) -> date:
    return v if isinstance(v, date) and not hasattr(v, "hour") else (v.date() if hasattr(v, "date") else date.fromisoformat(str(v)))


def load_costs_config(path: str | Path) -> CostsConfig:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    versions = []
    for v in raw["versions"]:
        fees = v["fees"]
        versions.append(CostVersion(
            effective_date=_as_date(v["effective_date"]),
            cogs_per_unit=dict(v["cogs_per_unit"]),
            packaging_per_unit=dict(v["packaging_per_unit"]),
            shipping_shopify_per_order=float(v["shipping_shopify_per_order"]),
            shopify_gateway_pct=float(fees["shopify_gateway_pct"]),
            shopify_gateway_fixed=float(fees["shopify_gateway_fixed"]),
            amazon_referral_pct=float(fees["amazon_referral_pct"]),
            amazon_fba_per_unit=float(fees["amazon_fba_per_unit"]),
            returns_provision_pct=dict(v["returns_provision_pct"]),
            flipkart_commission_pct=float(fees.get("flipkart_commission_pct", 0.0)),
            flipkart_shipping_per_unit=float(fees.get("flipkart_shipping_per_unit", 0.0)),
        ))
    versions.sort(key=lambda v: v.effective_date)
    return CostsConfig(versions=versions)


def upsert_cost_version(path: str | Path, version: CostVersion) -> CostsConfig:
    """Add ``version`` to costs.yaml, or replace the existing version with the
    same ``effective_date`` (so re-saving a same-day edit doesn't pile up
    duplicate entries). The file's leading comment header is preserved
    verbatim; per-version inline comments are not, since they're rewritten
    from the dataclass on every save."""
    path = Path(path)
    raw = path.read_text(encoding="utf-8")
    header = raw[: raw.index("versions:")]

    existing = load_costs_config(path)
    versions = [v for v in existing.versions if v.effective_date != version.effective_date]
    versions.append(version)
    versions.sort(key=lambda v: v.effective_date)

    body = {
        "versions": [
            {
                "effective_date": v.effective_date,
                "cogs_per_unit": v.cogs_per_unit,
                "packaging_per_unit": v.packaging_per_unit,
                "shipping_shopify_per_order": v.shipping_shopify_per_order,
                "fees": {
                    "shopify_gateway_pct": v.shopify_gateway_pct,
                    "shopify_gateway_fixed": v.shopify_gateway_fixed,
                    "amazon_referral_pct": v.amazon_referral_pct,
                    "amazon_fba_per_unit": v.amazon_fba_per_unit,
                    "flipkart_commission_pct": v.flipkart_commission_pct,
                    "flipkart_shipping_per_unit": v.flipkart_shipping_per_unit,
                },
                "returns_provision_pct": v.returns_provision_pct,
            }
            for v in versions
        ]
    }
    path.write_text(header + yaml.dump(body, sort_keys=False, default_flow_style=False), encoding="utf-8")
    return load_costs_config(path)


def shopify_line_economics(orders_df: pd.DataFrame, items_df: pd.DataFrame, costs: CostsConfig) -> pd.DataFrame:
    """Per order_item row. Order-level shared costs (shipping, gateway fees,
    discount) are allocated across a Shopify order's non-refund lines
    proportional to their share of the order's gross revenue; a refund line
    reverses COGS and packaging (the product came back) but not shipping or
    the gateway fee (Hayah Care already paid the courier and the gateway
    doesn't return its cut)."""
    df = items_df.merge(
        orders_df[["order_id", "created_at", "total", "discount_amount"]],
        on="order_id", how="left",
    ).reset_index(drop=True)

    versions = [costs.for_date(_as_date(d)) for d in df["created_at"]]
    df["cogs_per_unit"] = [v.cogs_per_unit.get(pid, 0.0) for v, pid in zip(versions, df["product_id"])]
    df["packaging_per_unit"] = [v.packaging_per_unit.get(pid, 0.0) for v, pid in zip(versions, df["product_id"])]
    gateway_pct = pd.Series([v.shopify_gateway_pct for v in versions], index=df.index)
    gateway_fixed = pd.Series([v.shopify_gateway_fixed for v in versions], index=df.index)
    shipping_per_order = pd.Series([v.shipping_shopify_per_order for v in versions], index=df.index)
    returns_pct = pd.Series([v.returns_provision_pct.get("shopify", 0.0) for v in versions], index=df.index)

    df["cogs"] = df["quantity"] * df["cogs_per_unit"]
    df["packaging"] = df["quantity"] * df["packaging_per_unit"]

    is_refund = df["is_refund_line"].astype(bool)
    nonrefund_revenue = df["line_amount"].where(~is_refund, 0.0)
    order_nonrefund_total = nonrefund_revenue.groupby(df["order_id"]).transform("sum")
    revenue_share = (nonrefund_revenue / order_nonrefund_total).where(order_nonrefund_total != 0, 0.0)

    order_gateway_fee = df["total"] * gateway_pct + gateway_fixed
    df["fees"] = order_gateway_fee * revenue_share
    df["shipping"] = shipping_per_order * revenue_share

    discount_allocated = (df["discount_amount"] * revenue_share).where(~is_refund, 0.0)
    df["net_revenue"] = df["line_amount"] - discount_allocated

    df["returns_provision"] = (df["net_revenue"] * returns_pct).where(~is_refund, 0.0)

    df["contribution_before_ad_spend"] = (
        df["net_revenue"] - df["cogs"] - df["packaging"] - df["shipping"] - df["fees"] - df["returns_provision"]
    )
    # weight for allocating ad spend by units actually sold — a refund line
    # (negative quantity) gets none, it doesn't deserve credit for spend
    df["ad_weight"] = df["quantity"].clip(lower=0)
    return df


AGG_COLS = ["net_revenue", "cogs", "packaging", "shipping", "fees", "returns_provision", "contribution_before_ad_spend"]


def shopify_order_economics(orders_df: pd.DataFrame, items_df: pd.DataFrame, costs: CostsConfig) -> pd.DataFrame:
    """One row per Shopify order — the line economics rolled up."""
    lines = shopify_line_economics(orders_df, items_df, costs)
    grouped = lines.groupby("order_id")[AGG_COLS].sum().reset_index()
    return grouped.merge(
        orders_df[["order_id", "created_at", "channel", "financial_status"]],
        on="order_id", how="left",
    )


def shopify_sku_economics(orders_df: pd.DataFrame, items_df: pd.DataFrame, costs: CostsConfig) -> pd.DataFrame:
    """Line economics rolled up by product_id instead of by order."""
    lines = shopify_line_economics(orders_df, items_df, costs)
    grouped = lines.groupby("product_id")[AGG_COLS + ["quantity"]].sum().reset_index()
    return grouped.rename(columns={"quantity": "units"})


def amazon_sku_day_economics(traffic_df: pd.DataFrame, costs: CostsConfig) -> pd.DataFrame:
    """One row per (date, product_id) — the only grain Amazon gives us."""
    df = traffic_df.copy().reset_index(drop=True)
    versions = [costs.for_date(_as_date(d)) for d in df["date"]]

    cogs_per_unit = [v.cogs_per_unit.get(pid, 0.0) for v, pid in zip(versions, df["product_id"])]
    packaging_per_unit = [v.packaging_per_unit.get(pid, 0.0) for v, pid in zip(versions, df["product_id"])]
    referral_pct = pd.Series([v.amazon_referral_pct for v in versions], index=df.index)
    fba_per_unit = pd.Series([v.amazon_fba_per_unit for v in versions], index=df.index)
    returns_pct = pd.Series([v.returns_provision_pct.get("amazon", 0.0) for v in versions], index=df.index)

    df["net_revenue"] = df["ordered_product_sales"]
    df["cogs"] = df["units_ordered"] * pd.Series(cogs_per_unit, index=df.index)
    df["packaging"] = df["units_ordered"] * pd.Series(packaging_per_unit, index=df.index)
    df["fees"] = df["net_revenue"] * referral_pct + df["units_ordered"] * fba_per_unit
    df["shipping"] = 0.0  # Amazon shipping is folded into the FBA fee, not billed separately
    df["returns_provision"] = df["net_revenue"] * returns_pct
    df["contribution_before_ad_spend"] = (
        df["net_revenue"] - df["cogs"] - df["packaging"] - df["shipping"] - df["fees"] - df["returns_provision"]
    )
    return df


def flipkart_sku_day_economics(traffic_df: pd.DataFrame, costs: CostsConfig) -> pd.DataFrame:
    """One row per (date, product_id) — same grain as Amazon's, for the same
    reason: Flipkart Seller Hub gives sellers a daily aggregate, not an
    order-level export. Fee shape differs from Amazon's referral+FBA model:
    Flipkart bills a flat commission % plus a per-unit shipping/collection
    fee rather than folding shipping into one all-in per-unit fee."""
    df = traffic_df.copy().reset_index(drop=True)
    versions = [costs.for_date(_as_date(d)) for d in df["date"]]

    cogs_per_unit = [v.cogs_per_unit.get(pid, 0.0) for v, pid in zip(versions, df["product_id"])]
    packaging_per_unit = [v.packaging_per_unit.get(pid, 0.0) for v, pid in zip(versions, df["product_id"])]
    commission_pct = pd.Series([v.flipkart_commission_pct for v in versions], index=df.index)
    shipping_per_unit = pd.Series([v.flipkart_shipping_per_unit for v in versions], index=df.index)
    returns_pct = pd.Series([v.returns_provision_pct.get("flipkart", 0.0) for v in versions], index=df.index)

    df["net_revenue"] = df["ordered_product_sales"]
    df["cogs"] = df["units_ordered"] * pd.Series(cogs_per_unit, index=df.index)
    df["packaging"] = df["units_ordered"] * pd.Series(packaging_per_unit, index=df.index)
    df["fees"] = df["net_revenue"] * commission_pct
    df["shipping"] = df["units_ordered"] * shipping_per_unit
    df["returns_provision"] = df["net_revenue"] * returns_pct
    df["contribution_before_ad_spend"] = (
        df["net_revenue"] - df["cogs"] - df["packaging"] - df["shipping"] - df["fees"] - df["returns_provision"]
    )
    return df


def apply_ad_spend(econ_df: pd.DataFrame, total_ad_spend: float, weight_col: str | None) -> pd.DataFrame:
    """Blend ``total_ad_spend`` across rows — evenly if weight_col is None
    (one Shopify order = one weight), or proportional to weight_col (Amazon
    rows, weighted by units_ordered, since there's no per-order grain)."""
    df = econ_df.copy()
    weights = pd.Series(1.0, index=df.index) if weight_col is None else df[weight_col].astype(float)
    total_weight = weights.sum()
    per_unit = (total_ad_spend / total_weight) if total_weight else 0.0
    df["allocated_ad_spend"] = weights * per_unit
    df["contribution_margin"] = df["contribution_before_ad_spend"] - df["allocated_ad_spend"]
    df["contribution_margin_pct"] = (df["contribution_margin"] / df["net_revenue"]).where(df["net_revenue"] != 0, 0.0)
    return df


def rollup(df_with_ad_spend: pd.DataFrame, by: str | list[str], extra_sum_cols: list[str] | None = None) -> pd.DataFrame:
    """Group a line/day table that already has ``allocated_ad_spend`` and
    ``contribution_margin`` (i.e. has been through ``apply_ad_spend``) up to
    order or SKU grain, and recompute the margin % from the summed dollars —
    never by averaging a percentage."""
    cols = AGG_COLS + ["allocated_ad_spend", "contribution_margin"] + (extra_sum_cols or [])
    grouped = df_with_ad_spend.groupby(by)[cols].sum().reset_index()
    grouped["contribution_margin_pct"] = (
        grouped["contribution_margin"] / grouped["net_revenue"]
    ).where(grouped["net_revenue"] != 0, 0.0)
    return grouped


def channel_summary(channel_frames: list[tuple[str, pd.DataFrame]], min_sample: int = 30) -> pd.DataFrame:
    """Every channel side by side — never blended into one number, because
    cost structure and even data grain differ channel to channel. Sample
    size is order count for Shopify and total units for a marketplace
    channel (its closest analog, since it has no discrete orders); either
    way, fewer than ``min_sample`` sets low_confidence so a thin channel
    isn't read as fact. Takes a list, not fixed shopify/amazon parameters,
    so a new channel (Flipkart, and whatever comes after it) is a longer
    list, not a signature change.
    """
    rows = []
    for channel, df in channel_frames:
        if df.empty:
            sample_size, net_revenue, contribution_margin = 0, 0.0, 0.0
        else:
            sample_size = int(df["units_ordered"].sum()) if "units_ordered" in df.columns else len(df)
            net_revenue = float(df["net_revenue"].sum())
            contribution_margin = float(df["contribution_margin"].sum())
        contribution_margin_pct = (contribution_margin / net_revenue) if net_revenue else 0.0
        rows.append({
            "channel": channel,
            "sample_size": sample_size,
            "low_confidence": sample_size < min_sample,
            "net_revenue": net_revenue,
            "contribution_margin": contribution_margin,
            "contribution_margin_pct": contribution_margin_pct,
        })
    return pd.DataFrame(rows)
