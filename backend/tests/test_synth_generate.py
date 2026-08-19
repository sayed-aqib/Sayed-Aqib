import csv
from datetime import date
from pathlib import Path

from backend.synth.generate import generate

END_DATE = date(2026, 8, 19)
DAYS = 182
SEED = 42


def _generate(tmp_path: Path) -> Path:
    out_dir = tmp_path / "raw"
    generate(seed=SEED, days=DAYS, end_date=END_DATE, out_dir=out_dir, n_customers=260)
    return out_dir


def _read_rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_reproducible_with_same_seed(tmp_path):
    out_a = _generate(tmp_path / "a")
    out_b = _generate(tmp_path / "b")

    files_a = sorted(p.relative_to(out_a) for p in out_a.rglob("*.csv"))
    files_b = sorted(p.relative_to(out_b) for p in out_b.rglob("*.csv"))
    assert files_a == files_b

    for rel in files_a:
        assert (out_a / rel).read_bytes() == (out_b / rel).read_bytes()


def test_all_sources_produce_nonempty_files(tmp_path):
    out_dir = _generate(tmp_path)
    expected_sources = [
        "shopify_orders/orders_export.csv",
        "shopify_customers/customers_export.csv",
        "shopify_sessions_daily/sessions_by_day.csv",
        "shopify_sessions_referrer/sessions_by_referrer.csv",
        "shopify_abandoned_checkouts/abandoned_checkouts.csv",
        "amazon_detail_page_sales_traffic/detail_page_sales_traffic.csv",
        "amazon_search_query_performance/search_query_performance.csv",
        "amazon_sp_campaign_report/sp_campaign_report.csv",
        "amazon_sp_search_term_report/sp_search_term_report.csv",
        "amazon_returns/amazon_returns.csv",
        "meta_ads_insights/meta_ads_insights.csv",
    ]
    for rel in expected_sources:
        rows = _read_rows(out_dir / rel)
        assert len(rows) > 0, f"{rel} produced no rows"


def test_shopify_orders_are_messy_on_purpose(tmp_path):
    out_dir = _generate(tmp_path)
    rows = _read_rows(out_dir / "shopify_orders" / "orders_export.csv")

    created_ats = {r["Created at"] for r in rows}
    # dates should not all share one format — several distinct string shapes
    date_shapes = {len(v) for v in created_ats}
    assert len(date_shapes) > 2, "expected mixed date formats in Created at"

    assert any(r["Phone"] == "" for r in rows), "expected some blank phone numbers"

    assert any(int(r["Lineitem quantity"]) < 0 for r in rows), "expected refund lines as negative quantities"

    names = {r["Lineitem name"] for r in rows}
    assert "Mom's Mix 400g" in names and "Mom's Supermix 400g" in names, (
        "expected the mid-range SKU rename to produce both old and new names"
    )

    seen = set()
    dupe_found = False
    for r in rows:
        key = tuple(r.items())
        if key in seen:
            dupe_found = True
            break
        seen.add(key)
    assert dupe_found, "expected at least one accidental duplicate row"


def test_mom_supermix_uses_old_name_before_cutover_and_new_after(tmp_path):
    out_dir = _generate(tmp_path)
    rows = _read_rows(out_dir / "shopify_orders" / "orders_export.csv")
    old_skus = {r["Lineitem sku"] for r in rows if r["Lineitem name"] == "Mom's Mix 400g"}
    new_skus = {r["Lineitem sku"] for r in rows if r["Lineitem name"] == "Mom's Supermix 400g"}
    assert old_skus == {"MOM-MIX-400"}
    assert new_skus == {"MOM-400"}
