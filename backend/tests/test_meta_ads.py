import pandas as pd
import pytest

from backend.metrics.meta_ads import (
    breakeven_economics,
    creative_fatigue_flags,
    load_meta_rules,
    recommend_budget_actions,
    rolling_adset_metrics,
)

RULES_PATH = "backend/config/meta_rules.yaml"


def test_load_meta_rules_parses_real_config():
    rules = load_meta_rules(RULES_PATH)
    assert rules["scale"]["roas_multiple_of_breakeven"] == 1.2
    assert rules["guardrails"]["max_budget_change_pct"] == 0.25


def test_breakeven_economics():
    df = pd.DataFrame({
        "net_revenue": [1000.0, 1000.0],
        "contribution_before_ad_spend": [400.0, 400.0],
    })
    result = breakeven_economics(df)
    assert result["contribution_margin_ratio"] == pytest.approx(0.4)
    assert result["breakeven_roas"] == pytest.approx(2.5)
    assert result["allowable_cpa"] == pytest.approx(400.0)
    assert result["sample_size"] == 2


def test_rolling_adset_metrics_aggregates_and_computes_rates():
    df = pd.DataFrame([
        {"campaign_name": "C1", "adset_name": "A1", "spend": 100.0, "impressions": 10000, "clicks": 100,
         "purchases": 2, "revenue": 400.0, "frequency": 1.5, "new_customers": 1},
        {"campaign_name": "C1", "adset_name": "A1", "spend": 100.0, "impressions": 10000, "clicks": 100,
         "purchases": 3, "revenue": 600.0, "frequency": 1.7, "new_customers": 2},
    ])
    result = rolling_adset_metrics(df)
    row = result.iloc[0]
    assert row["spend"] == 200.0
    assert row["purchases"] == 5
    assert row["revenue"] == 1000.0
    assert row["roas"] == pytest.approx(5.0)
    assert row["cpa"] == pytest.approx(40.0)
    assert row["ctr"] == pytest.approx(200 / 20000)
    assert row["cpm"] == pytest.approx(200 / 20000 * 1000)
    assert row["new_customer_share"] == pytest.approx(3 / 5)
    assert row["frequency"] == pytest.approx(1.6)


def test_creative_fatigue_flags_detects_frequency_and_ctr_drop():
    dates = pd.date_range("2026-01-01", periods=14, freq="D")
    rows = []
    for i, d in enumerate(dates):
        fatigued = i >= 7
        rows.append({
            "date": d, "campaign_name": "C1", "adset_name": "A1",
            "impressions": 1000, "clicks": 8 if fatigued else 20,
            "frequency": 3.0 if fatigued else 1.5,
        })
    df = pd.DataFrame(rows)
    rules = {"creative_fatigue": {"min_frequency": 2.5, "ctr_drop_from_peak_pct": 0.30}}
    result = creative_fatigue_flags(df, rules)
    row = result.iloc[0]
    assert bool(row["is_fatigued"]) is True


def test_creative_fatigue_flags_not_fatigued_when_frequency_is_low():
    dates = pd.date_range("2026-01-01", periods=14, freq="D")
    rows = [
        {"date": d, "campaign_name": "C1", "adset_name": "A1", "impressions": 1000, "clicks": 15, "frequency": 1.5}
        for d in dates
    ]
    df = pd.DataFrame(rows)
    rules = {"creative_fatigue": {"min_frequency": 2.5, "ctr_drop_from_peak_pct": 0.30}}
    result = creative_fatigue_flags(df, rules)
    assert bool(result.iloc[0]["is_fatigued"]) is False


def _adset_row(campaign, adset, roas, purchases, spend):
    return {"campaign_name": campaign, "adset_name": adset, "roas": roas, "purchases": purchases, "spend": spend}


def test_recommend_budget_actions_covers_every_rule():
    metrics_df = pd.DataFrame([
        _adset_row("C1", "Scale", 3.5, 10, 5000.0),
        _adset_row("C1", "Hold", 2.4, 8, 4000.0),
        _adset_row("C1", "Cut", 1.5, 4, 3500.0),
        _adset_row("C1", "Pause", 1.0, 6, 4000.0),
        _adset_row("C1", "TooFewPurchases", 1.0, 2, 5000.0),
        _adset_row("C1", "TooLittleSpend", 3.0, 5, 2000.0),
        _adset_row("C1", "TooNew", 5.0, 20, 6000.0),
    ])
    breakeven = {"breakeven_roas": 2.5, "allowable_cpa": 400.0}
    rules = load_meta_rules(RULES_PATH)
    adset_age_days = {
        ("C1", "Scale"): 30, ("C1", "Hold"): 30, ("C1", "Cut"): 30, ("C1", "Pause"): 30,
        ("C1", "TooFewPurchases"): 30, ("C1", "TooLittleSpend"): 30, ("C1", "TooNew"): 3,
    }
    result = recommend_budget_actions(metrics_df, breakeven, rules, adset_age_days).set_index("adset_name")

    assert result.loc["Scale", "rule"] == "scale"
    assert result.loc["Scale", "recommended_change_pct"] == pytest.approx(0.20)
    assert pd.isna(result.loc["Scale", "capped_from_pct"])

    assert result.loc["Hold", "rule"] == "hold"

    assert result.loc["Cut", "rule"] == "cut"
    assert result.loc["Cut", "recommended_change_pct"] == pytest.approx(-0.25)   # capped by guardrail
    assert result.loc["Cut", "capped_from_pct"] == pytest.approx(-0.30)

    assert result.loc["Pause", "rule"] == "pause"
    assert result.loc["TooFewPurchases", "rule"] == "insufficient_data"
    assert result.loc["TooLittleSpend", "rule"] == "insufficient_data"
    assert result.loc["TooNew", "rule"] == "too_new"

    # every row must carry reasoning and a confidence label — never a bare recommendation
    assert result["reasoning"].apply(lambda r: len(r) > 0).all()
    assert set(result["confidence"]) <= {"low", "medium", "high"}
