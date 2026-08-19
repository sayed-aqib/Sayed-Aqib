import pandas as pd
import pytest

from backend.metrics.keywords import classify_search_queries


def _rows():
    # four weeks aren't needed — one row per query is enough since the
    # metric sums whatever window it's given
    return pd.DataFrame([
        # gets plenty of impressions, poor click rate -> listing/image problem
        {"search_query": "healthy snacks", "impressions": 1000, "clicks": 10, "cart_adds": 3, "purchases": 1},
        # good click rate, but very few of those clicks convert -> price/review problem
        {"search_query": "trail mix online", "impressions": 1000, "clicks": 150, "cart_adds": 10, "purchases": 2},
        # healthy on both counts
        {"search_query": "hayah care", "impressions": 1000, "clicks": 140, "cart_adds": 40, "purchases": 30},
        # a query with zero data shouldn't crash the medians
        {"search_query": "kappi podi", "impressions": 0, "clicks": 0, "cart_adds": 0, "purchases": 0},
    ])


def test_classify_search_queries_computes_shares():
    result = classify_search_queries(_rows())
    row = result[result["search_query"] == "healthy snacks"].iloc[0]
    assert row["click_rate"] == pytest.approx(10 / 1000)
    assert row["purchase_rate"] == pytest.approx(1 / 10)
    assert row["impression_share"] == pytest.approx(1000 / 3000)  # 3 queries have impressions
    assert row["conversion_share"] == pytest.approx(1 / 33)


def test_classify_search_queries_flags_listing_problem_for_low_click_rate():
    result = classify_search_queries(_rows())
    row = result[result["search_query"] == "healthy snacks"].iloc[0]
    assert row["issue"] == "listing_or_image_problem"


def test_classify_search_queries_flags_price_or_review_problem_for_low_purchase_rate():
    result = classify_search_queries(_rows())
    row = result[result["search_query"] == "trail mix online"].iloc[0]
    assert row["issue"] == "price_or_review_problem"


def test_classify_search_queries_healthy_query_not_flagged():
    result = classify_search_queries(_rows())
    row = result[result["search_query"] == "hayah care"].iloc[0]
    assert row["issue"] == "healthy"


def test_classify_search_queries_low_confidence_under_three_purchases():
    result = classify_search_queries(_rows())
    row = result[result["search_query"] == "healthy snacks"].iloc[0]
    assert bool(row["low_confidence"]) is True  # only 1 purchase
    row2 = result[result["search_query"] == "hayah care"].iloc[0]
    assert bool(row2["low_confidence"]) is False  # 30 purchases


def test_classify_search_queries_handles_zero_impressions_query_without_crashing():
    result = classify_search_queries(_rows())
    row = result[result["search_query"] == "kappi podi"].iloc[0]
    assert row["click_rate"] == 0.0
    assert row["impression_share"] == 0.0
