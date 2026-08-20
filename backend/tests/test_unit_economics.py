from datetime import date, datetime

import pandas as pd
import pytest

from backend.metrics.unit_economics import (
    CostVersion,
    amazon_sku_day_economics,
    apply_ad_spend,
    channel_summary,
    load_costs_config,
    rollup,
    shopify_line_economics,
    shopify_order_economics,
    upsert_cost_version,
)

COSTS_PATH = "backend/config/costs.yaml"


def _costs():
    return load_costs_config(COSTS_PATH)


def test_costs_config_picks_the_version_effective_on_the_order_date():
    costs = _costs()
    v = costs.for_date(date(2026, 3, 1))
    assert v.effective_date == date(2026, 1, 1)
    assert v.cogs_per_unit["NSS-400"] == 320.0


def test_costs_config_a_new_version_does_not_change_the_past():
    costs = load_costs_config(COSTS_PATH)
    costs.versions.append(
        type(costs.versions[0])(
            effective_date=date(2026, 6, 1),
            cogs_per_unit={"NSS-400": 999.0},
            packaging_per_unit={"NSS-400": 25.0},
            shipping_shopify_per_order=90.0,
            shopify_gateway_pct=0.02,
            shopify_gateway_fixed=3.0,
            amazon_referral_pct=0.15,
            amazon_fba_per_unit=65.0,
            returns_provision_pct={"shopify": 0.02, "amazon": 0.04},
        )
    )
    # a March order still prices at the old (January) cost, not the June one
    march_version = costs.for_date(date(2026, 3, 1))
    assert march_version.cogs_per_unit["NSS-400"] == 320.0
    july_version = costs.for_date(date(2026, 7, 1))
    assert july_version.cogs_per_unit["NSS-400"] == 999.0


def _new_version(effective_date: date, nss_cogs: float) -> CostVersion:
    return CostVersion(
        effective_date=effective_date,
        cogs_per_unit={"NSS-400": nss_cogs},
        packaging_per_unit={"NSS-400": 25.0},
        shipping_shopify_per_order=90.0,
        shopify_gateway_pct=0.02,
        shopify_gateway_fixed=3.0,
        amazon_referral_pct=0.15,
        amazon_fba_per_unit=65.0,
        returns_provision_pct={"shopify": 0.02, "amazon": 0.04},
    )


def test_upsert_cost_version_appends_and_preserves_history(tmp_path):
    dest = tmp_path / "costs.yaml"
    dest.write_text(open(COSTS_PATH, encoding="utf-8").read(), encoding="utf-8")

    updated = upsert_cost_version(dest, _new_version(date(2026, 6, 1), 999.0))

    assert [v.effective_date for v in updated.versions] == [date(2026, 1, 1), date(2026, 6, 1)]
    assert updated.for_date(date(2026, 3, 1)).cogs_per_unit["NSS-400"] == 320.0
    assert updated.for_date(date(2026, 7, 1)).cogs_per_unit["NSS-400"] == 999.0
    # the file's explanatory header survives a save
    assert "Costs Hayah Care actually pays" in dest.read_text(encoding="utf-8")


def test_upsert_cost_version_same_effective_date_replaces_not_duplicates(tmp_path):
    dest = tmp_path / "costs.yaml"
    dest.write_text(open(COSTS_PATH, encoding="utf-8").read(), encoding="utf-8")

    upsert_cost_version(dest, _new_version(date(2026, 6, 1), 999.0))
    updated = upsert_cost_version(dest, _new_version(date(2026, 6, 1), 500.0))

    assert len(updated.versions) == 2
    assert updated.for_date(date(2026, 7, 1)).cogs_per_unit["NSS-400"] == 500.0


def _orders_df(rows: list[dict]) -> pd.DataFrame:
    base = {
        "order_id": None, "channel": "shopify", "created_at": None, "total": 0.0,
        "shipping": 0.0, "discount_amount": 0.0, "financial_status": "paid",
    }
    return pd.DataFrame([{**base, **r} for r in rows])


def _items_df(rows: list[dict]) -> pd.DataFrame:
    base = {
        "order_id": None, "line_seq": 0, "product_id": None, "quantity": 0,
        "unit_price": 0.0, "line_amount": 0.0, "is_refund_line": False,
    }
    return pd.DataFrame([{**base, **r} for r in rows])


def test_shopify_line_economics_simple_order():
    orders = _orders_df([
        {"order_id": "shopify:1", "created_at": datetime(2026, 2, 1), "total": 1100.0},
    ])
    items = _items_df([
        {"order_id": "shopify:1", "line_seq": 0, "product_id": "NSS-400", "quantity": 1,
         "unit_price": 999.0, "line_amount": 999.0},
    ])
    lines = shopify_line_economics(orders, items, _costs())
    row = lines.iloc[0]

    assert row["net_revenue"] == pytest.approx(999.0)
    assert row["cogs"] == pytest.approx(320.0)
    assert row["packaging"] == pytest.approx(25.0)
    assert row["shipping"] == pytest.approx(90.0)
    assert row["fees"] == pytest.approx(1100.0 * 0.02 + 3.0)
    assert row["returns_provision"] == pytest.approx(999.0 * 0.02)
    assert row["contribution_before_ad_spend"] == pytest.approx(
        999.0 - 320.0 - 25.0 - 90.0 - (1100.0 * 0.02 + 3.0) - (999.0 * 0.02)
    )


def test_shopify_order_economics_refund_reverses_cogs_but_not_shipping_or_fees():
    orders = _orders_df([
        {"order_id": "shopify:2", "created_at": datetime(2026, 2, 1), "total": 1100.0,
         "financial_status": "refunded"},
    ])
    items = _items_df([
        {"order_id": "shopify:2", "line_seq": 0, "product_id": "NSS-400", "quantity": 1,
         "unit_price": 999.0, "line_amount": 999.0, "is_refund_line": False},
        {"order_id": "shopify:2", "line_seq": 1, "product_id": "NSS-400", "quantity": -1,
         "unit_price": 999.0, "line_amount": -999.0, "is_refund_line": True},
    ])
    orders_econ = shopify_order_economics(orders, items, _costs())
    row = orders_econ.iloc[0]

    assert row["net_revenue"] == pytest.approx(0.0)
    assert row["cogs"] == pytest.approx(0.0)       # reversed: +320 then -320
    assert row["packaging"] == pytest.approx(0.0)  # reversed
    assert row["shipping"] == pytest.approx(90.0)  # already spent, not reversed
    assert row["fees"] == pytest.approx(1100.0 * 0.02 + 3.0)  # gateway doesn't refund its cut
    assert row["contribution_before_ad_spend"] == pytest.approx(
        0.0 - 90.0 - (1100.0 * 0.02 + 3.0) - (999.0 * 0.02)
    )


def test_amazon_sku_day_economics():
    traffic = pd.DataFrame([{
        "date": date(2026, 2, 1), "raw_asin": "B0HAYA0001", "product_id": "NSS-400",
        "units_ordered": 5, "ordered_product_sales": 4995.0,
    }])
    econ = amazon_sku_day_economics(traffic, _costs())
    row = econ.iloc[0]

    assert row["net_revenue"] == pytest.approx(4995.0)
    assert row["cogs"] == pytest.approx(5 * 320.0)
    assert row["packaging"] == pytest.approx(5 * 25.0)
    assert row["fees"] == pytest.approx(4995.0 * 0.15 + 5 * 65.0)
    assert row["returns_provision"] == pytest.approx(4995.0 * 0.04)
    assert row["contribution_before_ad_spend"] == pytest.approx(
        4995.0 - 5 * 320.0 - 5 * 25.0 - (4995.0 * 0.15 + 5 * 65.0) - 4995.0 * 0.04
    )


def test_apply_ad_spend_splits_evenly_across_unweighted_rows():
    econ = pd.DataFrame({
        "net_revenue": [1000.0, 1000.0],
        "contribution_before_ad_spend": [500.0, 500.0],
    })
    out = apply_ad_spend(econ, total_ad_spend=100.0, weight_col=None)
    assert out["allocated_ad_spend"].tolist() == pytest.approx([50.0, 50.0])
    assert out["contribution_margin"].tolist() == pytest.approx([450.0, 450.0])
    assert out["contribution_margin_pct"].tolist() == pytest.approx([0.45, 0.45])


def test_apply_ad_spend_weights_by_units():
    econ = pd.DataFrame({
        "units_ordered": [1, 4],
        "net_revenue": [999.0, 3996.0],
        "contribution_before_ad_spend": [400.0, 1600.0],
    })
    out = apply_ad_spend(econ, total_ad_spend=100.0, weight_col="units_ordered")
    assert out["allocated_ad_spend"].tolist() == pytest.approx([20.0, 80.0])


def test_ad_spend_rollup_by_sku_conserves_total_spend_and_recomputes_pct():
    orders = _orders_df([
        {"order_id": "shopify:1", "created_at": datetime(2026, 2, 1), "total": 1100.0},
        {"order_id": "shopify:2", "created_at": datetime(2026, 2, 2), "total": 700.0},
    ])
    items = _items_df([
        {"order_id": "shopify:1", "line_seq": 0, "product_id": "NSS-400", "quantity": 1,
         "unit_price": 999.0, "line_amount": 999.0},
        {"order_id": "shopify:2", "line_seq": 0, "product_id": "CK-2PK", "quantity": 2,
         "unit_price": 349.0, "line_amount": 698.0},
    ])
    lines = shopify_line_economics(orders, items, _costs())
    lines = apply_ad_spend(lines, total_ad_spend=300.0, weight_col="ad_weight")

    by_sku = rollup(lines, "product_id")
    assert by_sku["allocated_ad_spend"].sum() == pytest.approx(300.0)
    # 1 unit of NSS-400 vs 2 units of CK-2PK -> weights 1:2
    nss = by_sku[by_sku["product_id"] == "NSS-400"].iloc[0]
    ck = by_sku[by_sku["product_id"] == "CK-2PK"].iloc[0]
    assert nss["allocated_ad_spend"] == pytest.approx(100.0)
    assert ck["allocated_ad_spend"] == pytest.approx(200.0)
    assert nss["contribution_margin_pct"] == pytest.approx(nss["contribution_margin"] / nss["net_revenue"])


def test_channel_summary_flags_low_confidence_under_30_orders():
    shopify_econ = pd.DataFrame({
        "net_revenue": [999.0] * 10,
        "contribution_margin": [500.0] * 10,
    })
    amazon_econ = pd.DataFrame({
        "net_revenue": [4995.0] * 5,
        "units_ordered": [5] * 5,
        "contribution_margin": [1900.0] * 5,
    })
    summary = channel_summary(shopify_econ, amazon_econ, min_sample=30)
    shopify_row = summary[summary["channel"] == "shopify"].iloc[0]
    assert shopify_row["sample_size"] == 10
    assert bool(shopify_row["low_confidence"]) is True
    assert shopify_row["contribution_margin"] == pytest.approx(5000.0)
