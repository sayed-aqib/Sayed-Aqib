import csv
from datetime import date
from pathlib import Path

import duckdb
import pytest

from backend.ingest.run_all import run_all
from backend.ingest.shopify_orders import ingest_shopify_orders
from backend.models.ddl import init_db
from backend.synth.generate import generate

ORDER_FIELDS = [
    "Name", "Email", "Financial Status", "Paid at", "Fulfillment Status", "Currency",
    "Subtotal", "Shipping", "Taxes", "Total", "Discount Code", "Discount Amount",
    "Created at", "Lineitem quantity", "Lineitem name", "Lineitem price", "Lineitem sku",
    "Cancelled at", "Payment Method", "Refunded Amount", "Id", "Tags", "Phone",
    "Shipping City", "Shipping Province",
]


def _write_orders_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ORDER_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            base = {k: "" for k in ORDER_FIELDS}
            base.update(row)
            writer.writerow(base)


def _base_row(**overrides) -> dict:
    row = {
        "Name": "#1001",
        "Email": "someone@example.com",
        "Financial Status": "paid",
        "Paid at": "2026-01-05 10:00:00 +0530",
        "Fulfillment Status": "fulfilled",
        "Currency": "INR",
        "Subtotal": "999",
        "Shipping": "0",
        "Taxes": "50",
        "Total": "1049",
        "Created at": "2026-01-05 10:00:00 +0530",
        "Lineitem quantity": "1",
        "Lineitem name": "Nuts & Seeds Supermix 400g",
        "Lineitem price": "999",
        "Lineitem sku": "NSS-400",
        "Payment Method": "UPI",
        "Refunded Amount": "0",
        "Id": "1001",
        "Phone": "9876543210",
        "Shipping City": "Kozhikode",
        "Shipping Province": "Kerala",
    }
    row.update(overrides)
    return row


def test_synth_end_to_end_ingest_is_idempotent(tmp_path):
    raw_dir = tmp_path / "raw"
    generate(seed=1, days=60, end_date=date(2026, 8, 19), out_dir=raw_dir, n_customers=80)

    con = duckdb.connect(":memory:")
    init_db(con)

    run_all(con, raw_dir)
    counts_first = {
        t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in ["orders", "order_items", "customers", "ad_spend_daily", "returns"]
    }

    run_all(con, raw_dir)
    counts_second = {
        t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in ["orders", "order_items", "customers", "ad_spend_daily", "returns"]
    }

    assert counts_first == counts_second
    assert counts_first["orders"] > 0


def test_sku_rename_resolves_to_one_canonical_product(tmp_path):
    raw_dir = tmp_path / "raw"
    generate(seed=1, days=120, end_date=date(2026, 8, 19), out_dir=raw_dir, n_customers=80)

    con = duckdb.connect(":memory:")
    init_db(con)
    run_all(con, raw_dir)

    rows = con.execute(
        "SELECT DISTINCT raw_title, product_id FROM order_items WHERE raw_title LIKE 'Mom%'"
    ).fetchall()
    assert rows, "expected some Mom's Supermix / Mom's Mix line items"
    for raw_title, product_id in rows:
        assert product_id == "MOM-400", f"{raw_title!r} resolved to {product_id!r}, expected MOM-400"


def test_rejects_row_with_unparseable_date(tmp_path):
    csv_path = tmp_path / "orders_export.csv"
    _write_orders_csv(csv_path, [
        _base_row(),
        _base_row(Id="1002", Name="#1002", **{"Created at": "not-a-date"}),
    ])

    con = duckdb.connect(":memory:")
    init_db(con)
    result = ingest_shopify_orders(con, csv_path)

    assert result.rows_rejected == 1
    order_ids = {r[0] for r in con.execute("SELECT order_id FROM orders").fetchall()}
    assert "shopify:1002" not in order_ids
    assert "shopify:1001" in order_ids

    issue = con.execute("SELECT reason, severity FROM ingest_issues").fetchone()
    assert issue[1] == "rejected"
    assert "unparseable date" in issue[0]


def test_unmapped_sku_is_kept_with_null_product_and_logged_as_warning(tmp_path):
    csv_path = tmp_path / "orders_export.csv"
    _write_orders_csv(csv_path, [
        _base_row(Id="2001", Name="#2001", **{
            "Lineitem sku": "MYSTERY-SKU",
            "Lineitem name": "Some Product Nobody Mapped",
        }),
    ])

    con = duckdb.connect(":memory:")
    init_db(con)
    result = ingest_shopify_orders(con, csv_path)

    assert result.rows_rejected == 0
    item = con.execute(
        "SELECT product_id, raw_sku FROM order_items WHERE order_id = 'shopify:2001'"
    ).fetchone()
    assert item is not None, "row should still be inserted, just unmapped"
    assert item[0] is None
    assert item[1] == "MYSTERY-SKU"

    warnings = con.execute(
        "SELECT reason FROM ingest_issues WHERE severity = 'warning'"
    ).fetchall()
    assert any("unmapped SKU" in w[0] for w in warnings)


def test_shopify_refund_line_rolls_up_into_order_refunded_amount(tmp_path):
    csv_path = tmp_path / "orders_export.csv"
    _write_orders_csv(csv_path, [
        _base_row(Id="3001", Name="#3001", **{"Financial Status": "refunded", "Refunded Amount": "1049"}),
        _base_row(Id="3001", Name="#3001", **{
            "Lineitem quantity": "-1", "Subtotal": "-999", "Total": "-1049",
            "Refunded Amount": "0", "Fulfillment Status": "restocked",
        }),
    ])

    con = duckdb.connect(":memory:")
    init_db(con)
    ingest_shopify_orders(con, csv_path)

    order = con.execute(
        "SELECT total, refunded_amount FROM orders WHERE order_id = 'shopify:3001'"
    ).fetchone()
    assert order[0] == pytest.approx(1049)  # header reflects the original sale, not the refund line
    assert order[1] == pytest.approx(1049)

    items = con.execute(
        "SELECT quantity, is_refund_line FROM order_items WHERE order_id = 'shopify:3001' ORDER BY line_seq"
    ).fetchall()
    assert items[0] == (1, False)
    assert items[1] == (-1, True)
