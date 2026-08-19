"""Adapter for the Shopify orders export -> ``orders`` + ``order_items``.

One CSV row per line item; a refunded order also carries a negative-quantity
refund line (see backend/synth/generate.py). The order header (totals,
discount, dates) comes from the first non-refund line in the group — the
refund line's mirrored negative totals aren't the order's economics, they're
the adjustment, which is rolled up into ``orders.refunded_amount`` instead.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pydantic

from backend.ingest.common import (
    IngestIssue,
    IngestResult,
    dedupe_exact_rows,
    log_issues,
    read_csv_rows,
    upsert_rows,
    validate_rows,
)
from backend.ingest.sku_map import SkuMap
from backend.models.parsing import parse_flexible_date
from backend.models.schemas import ShopifyOrderRow

SOURCE = "shopify_orders"

ORDER_COLUMNS = [
    "order_id", "channel", "customer_id", "order_name", "created_at", "paid_at",
    "financial_status", "fulfillment_status", "currency", "subtotal", "shipping",
    "taxes", "discount_code", "discount_amount", "total", "refunded_amount",
    "payment_method", "shipping_city", "shipping_province", "source_file",
]
ITEM_COLUMNS = [
    "order_id", "line_seq", "product_id", "raw_sku", "raw_title", "quantity",
    "unit_price", "line_amount", "is_refund_line", "source_file",
]


def ingest_shopify_orders(con: duckdb.DuckDBPyConnection, path: Path, sku_map: SkuMap | None = None) -> IngestResult:
    sku_map = sku_map or SkuMap()
    file_label = path.name
    result = IngestResult(source=SOURCE, file=file_label)

    raw_rows = read_csv_rows(path)
    result.rows_read = len(raw_rows)
    deduped, n_dropped = dedupe_exact_rows(raw_rows)
    result.rows_deduped = n_dropped

    valid_rows, issues = validate_rows(deduped, ShopifyOrderRow)
    result.issues.extend(issues)
    result.rows_accepted = len(valid_rows)

    groups: dict[int, list[ShopifyOrderRow]] = {}
    for row in valid_rows:
        groups.setdefault(row.id, []).append(row)

    order_tuples: list[tuple] = []
    item_tuples: list[tuple] = []

    for order_id_num, rows in groups.items():
        header = next((r for r in rows if r.quantity > 0), rows[0])
        order_id = f"shopify:{order_id_num}"
        customer_id = f"shopify:{header.email.lower()}" if header.email else None
        if customer_id is None:
            result.issues.append(
                IngestIssue(row_number=None, severity="warning", reason=f"order {order_id} has no email; customer_id left blank")
            )

        refunded_amount = max((r.refunded_amount for r in rows), default=0.0)
        paid_at = parse_flexible_date(header.paid_at) if header.paid_at else None

        order_tuples.append((
            order_id, "shopify", customer_id, header.name, header.created_at,
            paid_at, header.financial_status, header.fulfillment_status, header.currency,
            header.subtotal, header.shipping, header.taxes, header.discount_code or None,
            header.discount_amount, header.total, refunded_amount,
            header.payment_method or None, header.shipping_city or None,
            header.shipping_province or None, file_label,
        ))

        for line_seq, row in enumerate(rows):
            is_refund_line = row.quantity < 0
            product_id = sku_map.resolve_shopify(row.lineitem_sku, row.lineitem_name)
            if product_id is None:
                result.issues.append(
                    IngestIssue(
                        row_number=None,
                        severity="warning",
                        reason=f"unmapped SKU on order {order_id}: sku={row.lineitem_sku!r} title={row.lineitem_name!r}",
                    )
                )
            item_tuples.append((
                order_id, line_seq, product_id, row.lineitem_sku or None, row.lineitem_name,
                row.quantity, row.lineitem_price, row.quantity * row.lineitem_price,
                is_refund_line, file_label,
            ))

    upsert_rows(con, "orders", ORDER_COLUMNS, order_tuples, ["order_id"])
    upsert_rows(con, "order_items", ITEM_COLUMNS, item_tuples, ["order_id", "line_seq"])
    log_issues(con, SOURCE, file_label, result.issues)
    return result
