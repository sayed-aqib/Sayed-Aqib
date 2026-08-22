"""Resolves whatever a channel calls a product back to a canonical product_id.

Backed by config/products.yaml (the catalog) and config/sku_map.yaml (the
aliases). Assume Amazon ASINs, Shopify SKUs, and any spreadsheet name will
not match each other or the catalog — an unresolved row is not silently
dropped, it's returned as ``None`` so the caller can log it and keep the row
with product_id left blank rather than losing revenue off the books.
"""

from __future__ import annotations

from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


class SkuMap:
    def __init__(
        self,
        products_path: Path = CONFIG_DIR / "products.yaml",
        map_path: Path = CONFIG_DIR / "sku_map.yaml",
    ) -> None:
        products_cfg = yaml.safe_load(products_path.read_text(encoding="utf-8"))["products"]
        self.product_ids = {p["product_id"] for p in products_cfg}

        map_cfg = yaml.safe_load(map_path.read_text(encoding="utf-8")) or {}
        self.shopify_sku_aliases: dict[str, str] = map_cfg.get("shopify_sku_aliases", {})
        self.amazon_asin_aliases: dict[str, str] = map_cfg.get("amazon_asin_aliases", {})
        self.flipkart_fsn_aliases: dict[str, str] = map_cfg.get("flipkart_fsn_aliases", {})
        self.title_aliases: dict[str, str] = map_cfg.get("title_aliases", {})

    def resolve_shopify(self, raw_sku: str, raw_title: str) -> str | None:
        if raw_sku in self.product_ids:
            return raw_sku
        if raw_sku in self.shopify_sku_aliases:
            return self.shopify_sku_aliases[raw_sku]
        if raw_title in self.title_aliases:
            return self.title_aliases[raw_title]
        return None

    def resolve_amazon(self, raw_asin: str, raw_title: str) -> str | None:
        if raw_asin in self.product_ids:
            return raw_asin
        if raw_asin in self.amazon_asin_aliases:
            return self.amazon_asin_aliases[raw_asin]
        if raw_title in self.title_aliases:
            return self.title_aliases[raw_title]
        return None

    def resolve_flipkart(self, raw_fsn: str, raw_title: str) -> str | None:
        if raw_fsn in self.product_ids:
            return raw_fsn
        if raw_fsn in self.flipkart_fsn_aliases:
            return self.flipkart_fsn_aliases[raw_fsn]
        if raw_title in self.title_aliases:
            return self.title_aliases[raw_title]
        return None
