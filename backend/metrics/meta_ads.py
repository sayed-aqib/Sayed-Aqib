"""Meta Ads budget module — advisory only. It recommends, she approves;
nothing here is ever pushed to Meta.

Everything is anchored to break-even ROAS (1 / contribution margin ratio),
not a target pulled from a blog post, and the line moves whenever her costs
move because it's computed fresh from Step 2's unit economics every time.
Budget recommendations are rules from config/meta_rules.yaml, not a model —
every recommendation carries the rule that fired, the numbers behind it,
and a confidence label from sample size alone, so she can disagree with it.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml


def load_meta_rules(path: str | Path) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def breakeven_economics(shopify_order_econ_df: pd.DataFrame) -> dict:
    """From Shopify order economics *before* ad spend (Step 2) — the ratio
    describes how much of each rupee of revenue is available to spend on
    acquiring it while still breaking even."""
    sample_size = len(shopify_order_econ_df)
    net_revenue = float(shopify_order_econ_df["net_revenue"].sum())
    contribution = float(shopify_order_econ_df["contribution_before_ad_spend"].sum())
    ratio = (contribution / net_revenue) if net_revenue else 0.0
    return {
        "contribution_margin_ratio": ratio,
        # None (not inf) when margin is zero or negative — there is no
        # ROAS that breaks even on a product losing money before ad spend
        "breakeven_roas": (1 / ratio) if ratio > 0 else None,
        "allowable_cpa": (contribution / sample_size) if sample_size else 0.0,
        "sample_size": sample_size,
    }


def rolling_adset_metrics(daily_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregates whatever window of daily rows the caller passes in (7-day
    or 28-day — the grouping is the same, only the input slice differs) to
    one row per (campaign, adset)."""
    grouped = daily_df.groupby(["campaign_name", "adset_name"]).agg(
        spend=("spend", "sum"),
        impressions=("impressions", "sum"),
        clicks=("clicks", "sum"),
        purchases=("purchases", "sum"),
        revenue=("revenue", "sum"),
        new_customers=("new_customers", "sum"),
        frequency=("frequency", "mean"),
    ).reset_index()

    grouped["roas"] = (grouped["revenue"] / grouped["spend"]).where(grouped["spend"] > 0, 0.0)
    grouped["cpa"] = (grouped["spend"] / grouped["purchases"]).where(grouped["purchases"] > 0, None)
    grouped["ctr"] = (grouped["clicks"] / grouped["impressions"]).where(grouped["impressions"] > 0, 0.0)
    grouped["cpm"] = (grouped["spend"] / grouped["impressions"] * 1000).where(grouped["impressions"] > 0, 0.0)
    grouped["new_customer_share"] = (grouped["new_customers"] / grouped["purchases"]).where(
        grouped["purchases"] > 0, 0.0
    )
    return grouped


def creative_fatigue_flags(daily_df: pd.DataFrame, rules: dict, window_days: int = 7) -> pd.DataFrame:
    """Frequency above the configured floor *and* the trailing rolling
    click-through rate down more than the configured share from its own
    peak over the history provided — "creative is tiring, not failing" is a
    different action from cutting budget, so it's flagged separately."""
    min_frequency = rules["creative_fatigue"]["min_frequency"]
    drop_share = rules["creative_fatigue"]["ctr_drop_from_peak_pct"]

    rows = []
    for (campaign, adset), g in daily_df.sort_values("date").groupby(["campaign_name", "adset_name"]):
        g = g.copy()
        g["daily_ctr"] = (g["clicks"] / g["impressions"]).where(g["impressions"] > 0, 0.0)
        rolling_ctr = g["daily_ctr"].rolling(window_days, min_periods=window_days).mean()
        peak_ctr = float(rolling_ctr.max()) if rolling_ctr.notna().any() else 0.0
        current_ctr = float(rolling_ctr.iloc[-1]) if rolling_ctr.notna().any() else 0.0
        current_frequency = float(g["frequency"].tail(window_days).mean())

        is_fatigued = current_frequency > min_frequency and current_ctr < peak_ctr * (1 - drop_share)
        rows.append({
            "campaign_name": campaign,
            "adset_name": adset,
            "current_frequency": current_frequency,
            "current_ctr_7d": current_ctr,
            "peak_ctr_7d": peak_ctr,
            "is_fatigued": is_fatigued,
        })
    return pd.DataFrame(rows)


def recommend_budget_actions(
    metrics_df: pd.DataFrame,
    breakeven: dict,
    rules: dict,
    adset_age_days: dict[tuple[str, str], int],
) -> pd.DataFrame:
    breakeven_roas = breakeven["breakeven_roas"]
    max_change = rules["guardrails"]["max_budget_change_pct"]
    rows = []

    for _, row in metrics_df.iterrows():
        key = (row["campaign_name"], row["adset_name"])
        age = adset_age_days.get(key, 0)
        roas, purchases, spend = row["roas"], row["purchases"], row["spend"]
        change_pct: float | None = None
        capped_from: float | None = None

        min_live_days = rules["guardrails"]["min_days_live_before_recommendation"]
        if breakeven_roas is None:
            rule = "hold"
            reason = "contribution margin is zero or negative this period — no break-even ROAS to judge spend against"
        elif age < min_live_days:
            rule = "too_new"
            reason = f"live {age} days — needs {min_live_days} before a recommendation"

        elif purchases < rules["insufficient_data"]["min_purchases"] or spend < rules["insufficient_data"]["min_spend"]:
            rule = "insufficient_data"
            reason = f"only {purchases:.0f} purchases on ₹{spend:,.0f} spent this week — hold until there's more signal"

        elif roas >= breakeven_roas * rules["scale"]["roas_multiple_of_breakeven"]:
            rule = "scale"
            raw = rules["scale"]["budget_change_pct"]
            change_pct = min(raw, max_change)
            capped_from = raw if change_pct != raw else None
            reason = f"ROAS {roas:.2f} is {roas / breakeven_roas:.1f}x break-even ({breakeven_roas:.2f})"

        elif abs(roas - breakeven_roas) <= breakeven_roas * rules["hold_band"]["roas_tolerance_pct"]:
            rule = "hold"
            reason = f"ROAS {roas:.2f} is within {rules['hold_band']['roas_tolerance_pct']:.0%} of break-even ({breakeven_roas:.2f})"

        elif roas < breakeven_roas * rules["pause"]["roas_multiple_of_breakeven"] and purchases >= rules["pause"]["min_purchases"]:
            rule = "pause"
            reason = f"ROAS {roas:.2f} is under half of break-even ({breakeven_roas:.2f}) on {purchases:.0f} purchases"

        elif roas < breakeven_roas and purchases >= rules["cut"]["min_purchases"]:
            rule = "cut"
            raw = rules["cut"]["budget_change_pct"]
            change_pct = max(raw, -max_change)
            capped_from = raw if change_pct != raw else None
            reason = f"ROAS {roas:.2f} is below break-even ({breakeven_roas:.2f}) on {purchases:.0f} purchases"

        else:
            rule = "hold"
            reason = f"ROAS {roas:.2f} is below break-even but only {purchases:.0f} purchases — not enough to act on"

        confidence = "high" if purchases >= 10 else ("medium" if purchases >= 3 else "low")

        rows.append({
            "campaign_name": row["campaign_name"],
            "adset_name": row["adset_name"],
            "rule": rule,
            "recommended_change_pct": change_pct,
            "capped_from_pct": capped_from,
            "reasoning": reason,
            "confidence": confidence,
        })

    return pd.DataFrame(rows)
