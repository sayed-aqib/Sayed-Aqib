"""Seeds the products table from config/products.yaml.

Not a CSV adapter like the others — the catalog is a business decision, not
something we ingest from an export.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import yaml

from backend.ingest.common import upsert_rows

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


def seed_products(con: duckdb.DuckDBPyConnection, path: Path = CONFIG_DIR / "products.yaml") -> int:
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))["products"]
    rows = [
        (p["product_id"], p["name"], ",".join(p["channels"]), float(p["list_price"]))
        for p in cfg
    ]
    upsert_rows(con, "products", ["product_id", "name", "channels", "list_price"], rows, ["product_id"])
    return len(rows)
