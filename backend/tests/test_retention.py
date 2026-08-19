from datetime import datetime

import pandas as pd
import pytest

from backend.metrics.retention import (
    cross_sell_from_chukku,
    customer_purchase_sequence,
    monthly_cohorts,
    reorder_gap_stats,
    repeat_purchase_rate,
    repeat_purchase_rate_by_first_sku,
)


def _orders(rows):
    base = {"order_id": None, "customer_id": None, "created_at": None}
    return pd.DataFrame([{**base, **r} for r in rows])


def _items(rows):
    base = {"order_id": None, "product_id": None, "quantity": 1, "line_amount": 0.0}
    return pd.DataFrame([{**base, **r} for r in rows])


def test_customer_purchase_sequence_tracks_first_sku_and_gap():
    orders = _orders([
        {"order_id": "o1", "customer_id": "c1", "created_at": datetime(2026, 1, 1)},
        {"order_id": "o2", "customer_id": "c1", "created_at": datetime(2026, 2, 10)},
        {"order_id": "o3", "customer_id": "c2", "created_at": datetime(2026, 1, 15)},
    ])
    items = _items([
        {"order_id": "o1", "product_id": "CK-2PK", "quantity": 2, "line_amount": 698.0},
        {"order_id": "o2", "product_id": "NSS-400", "quantity": 1, "line_amount": 999.0},
        {"order_id": "o3", "product_id": "NSS-400", "quantity": 1, "line_amount": 999.0},
    ])
    seq = customer_purchase_sequence(orders, items)
    c1 = seq[seq["customer_id"] == "c1"].iloc[0]
    assert c1["n_orders"] == 2
    assert c1["first_sku"] == "CK-2PK"
    assert c1["days_to_second_order"] == 40

    c2 = seq[seq["customer_id"] == "c2"].iloc[0]
    assert c2["n_orders"] == 1
    assert pd.isna(c2["days_to_second_order"])


def test_repeat_purchase_rate_overall():
    seq = pd.DataFrame({"customer_id": ["a", "b", "c", "d"], "n_orders": [2, 1, 3, 1]})
    result = repeat_purchase_rate(seq, min_sample=3)
    assert result["sample_size"] == 4
    assert result["repeat_customers"] == 2
    assert result["repeat_rate"] == pytest.approx(0.5)
    assert result["low_confidence"] is False


def test_repeat_purchase_rate_by_first_sku():
    seq = pd.DataFrame({
        "customer_id": ["a", "b", "c", "d", "e"],
        "n_orders": [2, 1, 1, 2, 2],
        "first_sku": ["CK-2PK", "CK-2PK", "NSS-400", "NSS-400", "NSS-400"],
    })
    result = repeat_purchase_rate_by_first_sku(seq, min_sample=3)
    ck = result[result["first_sku"] == "CK-2PK"].iloc[0]
    nss = result[result["first_sku"] == "NSS-400"].iloc[0]
    assert ck["repeat_rate"] == pytest.approx(0.5)
    assert ck["sample_size"] == 2
    assert bool(ck["low_confidence"]) is True   # only 2 customers, below min_sample=3
    assert nss["repeat_rate"] == pytest.approx(2 / 3)
    assert bool(nss["low_confidence"]) is False


def test_reorder_gap_stats_uses_median_and_ignores_one_time_buyers():
    seq = pd.DataFrame({
        "customer_id": ["a", "b", "c", "d"],
        "days_to_second_order": [10, 20, 30, None],
    })
    result = reorder_gap_stats(seq, min_sample=3)
    assert result["sample_size"] == 3
    assert result["median_days"] == pytest.approx(20)
    assert result["low_confidence"] is False


def test_monthly_cohorts_counts_orders_by_months_since_first():
    orders = _orders([
        {"order_id": "o1", "customer_id": "c1", "created_at": datetime(2026, 1, 5)},
        {"order_id": "o2", "customer_id": "c1", "created_at": datetime(2026, 2, 10)},
        {"order_id": "o3", "customer_id": "c2", "created_at": datetime(2026, 2, 1)},
        {"order_id": "o4", "customer_id": "c2", "created_at": datetime(2026, 2, 20)},
    ])
    result = monthly_cohorts(orders)
    jan_cohort = result[result["cohort_month"] == "2026-01"]
    assert jan_cohort[jan_cohort["months_since_first"] == 0]["order_count"].iloc[0] == 1
    assert jan_cohort[jan_cohort["months_since_first"] == 1]["order_count"].iloc[0] == 1

    feb_cohort = result[result["cohort_month"] == "2026-02"]
    # c2's two orders are both in month 0 of its own cohort
    assert feb_cohort[feb_cohort["months_since_first"] == 0]["order_count"].iloc[0] == 2


def test_cross_sell_from_chukku_counts_customers_who_later_buy_a_mix():
    orders = _orders([
        {"order_id": "o1", "customer_id": "c1", "created_at": datetime(2026, 1, 1)},
        {"order_id": "o2", "customer_id": "c1", "created_at": datetime(2026, 2, 1)},
        {"order_id": "o3", "customer_id": "c2", "created_at": datetime(2026, 1, 1)},
        {"order_id": "o4", "customer_id": "c2", "created_at": datetime(2026, 2, 1)},
        {"order_id": "o5", "customer_id": "c3", "created_at": datetime(2026, 1, 1)},
    ])
    items = _items([
        {"order_id": "o1", "product_id": "CK-2PK", "quantity": 2},
        {"order_id": "o2", "product_id": "NSS-400", "quantity": 1},   # c1 converts
        {"order_id": "o3", "product_id": "CK-2PK", "quantity": 2},
        {"order_id": "o4", "product_id": "CK-2PK", "quantity": 2},    # c2 buys more Chukku, no mix
        {"order_id": "o5", "product_id": "CK-2PK", "quantity": 2},    # c3: one-time buyer
    ])
    seq = customer_purchase_sequence(orders, items)
    result = cross_sell_from_chukku(seq, orders, items, min_sample=3)
    assert result["cohort_size"] == 3
    assert result["converted"] == 1
    assert result["conversion_rate"] == pytest.approx(1 / 3)
