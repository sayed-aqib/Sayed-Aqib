import pandas as pd
import pytest

from backend.metrics.funnel import amazon_funnel_by_product, shopify_funnel, shopify_referrer_split

MIN_SAMPLE = 30


def test_shopify_funnel_sums_and_computes_drop_off():
    df = pd.DataFrame([
        {"sessions": 100, "added_to_cart": 20, "reached_checkout": 10, "completed_checkout": 5},
        {"sessions": 200, "added_to_cart": 40, "reached_checkout": 20, "completed_checkout": 10},
    ])
    result = shopify_funnel(df, min_sample=MIN_SAMPLE)

    assert result["sessions"] == 300
    assert result["added_to_cart"] == 60
    assert result["reached_checkout"] == 30
    assert result["completed_checkout"] == 15

    # step-over-sessions rates
    assert result["added_to_cart_rate"] == pytest.approx(60 / 300)
    assert result["reached_checkout_rate"] == pytest.approx(30 / 300)
    assert result["completed_checkout_rate"] == pytest.approx(15 / 300)

    # step-over-previous-step drop-off
    assert result["drop_off_sessions_to_cart"] == pytest.approx(1 - 60 / 300)
    assert result["drop_off_cart_to_checkout"] == pytest.approx(1 - 30 / 60)
    assert result["drop_off_checkout_to_purchase"] == pytest.approx(1 - 15 / 30)

    assert result["low_confidence"] is True  # only 15 completed checkouts, below min_sample=30


def test_shopify_funnel_includes_home_and_product_page_views():
    df = pd.DataFrame([
        {
            "sessions": 100, "home_page_views": 70, "product_page_views": 40,
            "added_to_cart": 20, "reached_checkout": 10, "completed_checkout": 5,
        },
    ])
    result = shopify_funnel(df, min_sample=30)

    assert result["home_page_views"] == 70
    assert result["product_page_views"] == 40
    assert result["home_page_view_rate"] == pytest.approx(0.70)
    assert result["product_page_view_rate"] == pytest.approx(0.40)
    assert result["drop_off_sessions_to_home"] == pytest.approx(1 - 0.70)
    assert result["drop_off_home_to_product"] == pytest.approx(1 - 40 / 70)
    assert result["drop_off_product_to_cart"] == pytest.approx(1 - 20 / 40)


def test_shopify_funnel_falls_back_to_zero_when_page_view_columns_absent():
    # older-shaped input (e.g. before this column existed) shouldn't raise
    df = pd.DataFrame([{"sessions": 100, "added_to_cart": 20, "reached_checkout": 10, "completed_checkout": 5}])
    result = shopify_funnel(df, min_sample=30)
    assert result["home_page_views"] == 0
    assert result["product_page_view_rate"] == 0.0


def test_shopify_funnel_flags_low_confidence_on_thin_conversions():
    df = pd.DataFrame([
        {"sessions": 500, "added_to_cart": 50, "reached_checkout": 10, "completed_checkout": 2},
    ])
    result = shopify_funnel(df, min_sample=30)
    assert result["completed_checkout"] == 2
    assert result["low_confidence"] is True


def test_shopify_funnel_handles_empty_frame():
    df = pd.DataFrame(columns=["sessions", "added_to_cart", "reached_checkout", "completed_checkout"])
    result = shopify_funnel(df, min_sample=30)
    assert result["sessions"] == 0
    assert result["added_to_cart_rate"] == 0.0
    assert result["low_confidence"] is True


def test_shopify_referrer_split_classifies_paid_vs_organic():
    df = pd.DataFrame([
        {"referrer": "Facebook Ads", "sessions": 100},
        {"referrer": "Google Ads", "sessions": 50},
        {"referrer": "Direct", "sessions": 80},
        {"referrer": "Google (organic)", "sessions": 70},
        {"referrer": "(all)", "sessions": 9999},  # the day-level total row must be excluded
    ])
    result = shopify_referrer_split(df)
    assert result["paid_sessions"] == 150
    assert result["organic_sessions"] == 150
    assert result["paid_share"] == pytest.approx(0.5)


def test_amazon_funnel_by_product_computes_overall_unit_session_pct_not_average_of_daily():
    df = pd.DataFrame([
        {"product_id": "NSS-400", "sessions": 10, "units_ordered": 5},   # 50%
        {"product_id": "NSS-400", "sessions": 1000, "units_ordered": 10},  # 1%
    ])
    result = amazon_funnel_by_product(df, min_sample=30)
    row = result[result["product_id"] == "NSS-400"].iloc[0]
    # overall = 15 units / 1010 sessions, NOT the average of 50% and 1%
    assert row["unit_session_pct"] == pytest.approx(15 / 1010)
    assert row["sessions"] == 1010
    assert row["units_ordered"] == 15
