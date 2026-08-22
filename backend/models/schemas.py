"""Pydantic v2 schemas for raw rows coming off each source CSV.

Every ingest adapter validates each row against the matching schema here
before it's normalized into a warehouse table. A row that fails validation
is rejected and logged with the reason (see backend/ingest/common.py) — it
never silently disappears. Field aliases match the exact column names in the
real export, so a row dict straight out of csv.DictReader can be passed to
``Model.model_validate(row)``.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.models.parsing import parse_flexible_bool, parse_flexible_date


class _Row(BaseModel):
    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    @model_validator(mode="before")
    @classmethod
    def _blank_cells_fall_back_to_defaults(cls, data):
        """A blank CSV cell should mean "use the field's default", not fail
        to parse as a number. Required fields have no default, so dropping
        the key still surfaces a clear "missing" rejection for those."""
        if isinstance(data, dict):
            return {k: v for k, v in data.items() if v != ""}
        return data


class ShopifyOrderRow(_Row):
    id: int = Field(alias="Id")
    name: str = Field(alias="Name")
    email: str = Field(alias="Email")
    financial_status: str = Field(alias="Financial Status")
    paid_at: str = Field(default="", alias="Paid at")
    fulfillment_status: str = Field(default="", alias="Fulfillment Status")
    currency: str = Field(default="INR", alias="Currency")
    subtotal: float = Field(alias="Subtotal")
    shipping: float = Field(default=0.0, alias="Shipping")
    taxes: float = Field(default=0.0, alias="Taxes")
    total: float = Field(alias="Total")
    discount_code: str = Field(default="", alias="Discount Code")
    discount_amount: float = Field(default=0.0, alias="Discount Amount")
    created_at_raw: str = Field(alias="Created at")
    quantity: int = Field(alias="Lineitem quantity")
    lineitem_name: str = Field(alias="Lineitem name")
    lineitem_price: float = Field(alias="Lineitem price")
    lineitem_sku: str = Field(default="", alias="Lineitem sku")
    payment_method: str = Field(default="", alias="Payment Method")
    refunded_amount: float = Field(default=0.0, alias="Refunded Amount")
    phone: str = Field(default="", alias="Phone")
    shipping_city: str = Field(default="", alias="Shipping City")
    shipping_province: str = Field(default="", alias="Shipping Province")

    @field_validator("created_at_raw")
    @classmethod
    def _created_at_parseable(cls, v: str) -> str:
        parse_flexible_date(v)  # raises ValueError -> becomes a rejection
        return v

    @field_validator("lineitem_name")
    @classmethod
    def _name_nonempty(cls, v: str) -> str:
        if not v:
            raise ValueError("blank Lineitem name")
        return v

    @field_validator("quantity")
    @classmethod
    def _quantity_nonzero(cls, v: int) -> int:
        if v == 0:
            raise ValueError("zero quantity line")
        return v

    @property
    def created_at(self) -> datetime:
        return parse_flexible_date(self.created_at_raw)


class ShopifyCustomerRow(_Row):
    id: int = Field(alias="Id")
    first_name: str = Field(default="", alias="First Name")
    last_name: str = Field(default="", alias="Last Name")
    email: str = Field(alias="Email")
    accepts_marketing_raw: str = Field(default="no", alias="Accepts Marketing")
    city: str = Field(default="", alias="City")
    province: str = Field(default="", alias="Province")
    country: str = Field(default="", alias="Country")
    phone: str = Field(default="", alias="Phone")
    total_spent: float = Field(default=0.0, alias="Total Spent")
    total_orders: int = Field(default=0, alias="Total Orders")

    @property
    def accepts_marketing(self) -> bool:
        return parse_flexible_bool(self.accepts_marketing_raw)


class SessionDailyRow(_Row):
    date_raw: str = Field(alias="Date")
    sessions: int = Field(alias="Sessions")


class SessionReferrerRow(_Row):
    date_raw: str = Field(alias="Date")
    referrer: str = Field(alias="Referrer")
    sessions: int = Field(alias="Sessions")


class ShopifyFunnelDailyRow(_Row):
    date_raw: str = Field(alias="Date")
    sessions: int = Field(default=0, alias="Sessions")
    # No real Shopify export has these two yet -- Shopify's own analytics
    # export doesn't break sessions down by page. Placeholder column names,
    # populated on synthetic data until a real page-view source (Shopify's
    # own analytics, or GA4) is wired up -- see CLAUDE.md on fixing the
    # adapter and generator together when a real file's columns differ.
    home_page_views: int = Field(default=0, alias="Home Page Views")
    product_page_views: int = Field(default=0, alias="Product Page Views")
    added_to_cart: int = Field(default=0, alias="Added to Cart")
    reached_checkout: int = Field(default=0, alias="Reached Checkout")
    completed_checkout: int = Field(default=0, alias="Completed Checkout")


class AbandonedCheckoutRow(_Row):
    checkout_id: str = Field(alias="Checkout ID")
    created_at_raw: str = Field(alias="Created at")
    email: str = Field(default="", alias="Email")
    phone: str = Field(default="", alias="Phone")
    total: float = Field(alias="Total")
    currency: str = Field(default="INR", alias="Currency")
    items_in_cart: int = Field(default=0, alias="Items in Cart")
    recovered_raw: str = Field(default="no", alias="Recovered")

    @field_validator("created_at_raw")
    @classmethod
    def _created_at_parseable(cls, v: str) -> str:
        parse_flexible_date(v)
        return v

    @property
    def recovered(self) -> bool:
        return parse_flexible_bool(self.recovered_raw)


class AmazonProductTrafficRow(_Row):
    asin: str = Field(alias="(Child) ASIN")
    title: str = Field(default="", alias="Title")
    sessions: int = Field(default=0, alias="Sessions - Total")
    page_views: int = Field(default=0, alias="Page Views - Total")
    buybox_pct: float = Field(default=0.0, alias="Featured Offer (Buy Box) Percentage")
    units_ordered: int = Field(default=0, alias="Units Ordered")
    unit_session_pct: float = Field(default=0.0, alias="Unit Session Percentage")
    ordered_product_sales: float = Field(default=0.0, alias="Ordered Product Sales")
    date_raw: str = Field(alias="Date")


class SearchQueryRow(_Row):
    search_query: str = Field(alias="Search Query")
    week_start_raw: str = Field(alias="Week Start Date")
    impressions: int = Field(default=0, alias="Impressions: Total Count")
    clicks: int = Field(default=0, alias="Clicks: Total Count")
    click_rate_pct: float = Field(default=0.0, alias="Click Rate %")
    cart_adds: int = Field(default=0, alias="Cart Adds: Total Count")
    purchases: int = Field(default=0, alias="Purchases: Total Count")
    purchase_rate_pct: float = Field(default=0.0, alias="Purchase Rate %")

    @field_validator("search_query")
    @classmethod
    def _query_nonempty(cls, v: str) -> str:
        if not v:
            raise ValueError("blank search query")
        return v


class SpCampaignRow(_Row):
    date_raw: str = Field(alias="Date")
    campaign_name: str = Field(alias="Campaign Name")
    campaign_status: str = Field(default="", alias="Campaign Status")
    impressions: int = Field(default=0, alias="Impressions")
    clicks: int = Field(default=0, alias="Clicks")
    ctr: float = Field(default=0.0, alias="CTR")
    spend: float = Field(default=0.0, alias="Spend")
    cpc: float = Field(default=0.0, alias="CPC")
    orders: int = Field(default=0, alias="Orders")
    sales: float = Field(default=0.0, alias="Sales")
    acos: float = Field(default=0.0, alias="ACOS")


class SpSearchTermRow(_Row):
    date_raw: str = Field(alias="Date")
    campaign_name: str = Field(alias="Campaign Name")
    ad_group_name: str = Field(alias="Ad Group Name")
    match_type: str = Field(default="", alias="Match Type")
    search_term: str = Field(alias="Customer Search Term")
    impressions: int = Field(default=0, alias="Impressions")
    clicks: int = Field(default=0, alias="Clicks")
    spend: float = Field(default=0.0, alias="Spend")
    sales_7d: float = Field(default=0.0, alias="7 Day Total Sales")
    orders_7d: int = Field(default=0, alias="7 Day Total Orders (#)")


class AmazonReturnRow(_Row):
    return_date_raw: str = Field(alias="Return Date")
    order_id: str = Field(alias="Order ID")
    sku: str = Field(default="", alias="SKU")
    asin: str = Field(default="", alias="ASIN")
    reason: str = Field(default="", alias="Return Reason")
    quantity: int = Field(default=0, alias="Return Quantity")
    refund_amount: float = Field(default=0.0, alias="Refund Amount")


class FlipkartAdsCampaignRow(_Row):
    """Flipkart Ads (the platform's own sponsored-listing product) doesn't
    have a real export on file yet either — same placeholder-schema
    situation as FlipkartProductTrafficRow above. Modelled closely on
    Amazon's Sponsored Products campaign report shape since both are
    campaign-grain, no adset concept."""

    date_raw: str = Field(alias="Date")
    campaign_name: str = Field(alias="Campaign Name")
    campaign_status: str = Field(default="", alias="Campaign Status")
    views: int = Field(default=0, alias="Views")
    clicks: int = Field(default=0, alias="Clicks")
    ad_spend: float = Field(default=0.0, alias="Ad Spend")
    direct_units: int = Field(default=0, alias="Direct Units")
    direct_revenue: float = Field(default=0.0, alias="Direct Revenue")


class FlipkartProductTrafficRow(_Row):
    """Flipkart Seller Hub's sales/traffic report doesn't exist in the source
    list yet — no real export has been seen. Column names here are a
    best-guess placeholder in the same spirit as the other invented exports;
    per CLAUDE.md, fix this schema and backend/synth/generate.py together the
    day a real Flipkart file arrives."""

    fsn: str = Field(alias="FSN")
    title: str = Field(default="", alias="Product Title")
    sessions: int = Field(default=0, alias="Sessions")
    units_ordered: int = Field(default=0, alias="Units Sold")
    ordered_product_sales: float = Field(default=0.0, alias="GMV (INR)")
    date_raw: str = Field(alias="Date")


class MetaAdsRow(_Row):
    date_raw: str = Field(alias="Reporting starts")
    campaign_name: str = Field(alias="Campaign name")
    adset_name: str = Field(alias="Ad set name")
    spend: float = Field(default=0.0, alias="Amount spent (INR)")
    impressions: int = Field(default=0, alias="Impressions")
    reach: int = Field(default=0, alias="Reach")
    frequency: float = Field(default=0.0, alias="Frequency")
    cpm: float = Field(default=0.0, alias="CPM (cost per 1,000 impressions) (INR)")
    clicks: int = Field(default=0, alias="Clicks (all)")
    ctr_pct: float = Field(default=0.0, alias="CTR (all)")
    purchases: int = Field(default=0, alias="Purchases")
    revenue: float = Field(default=0.0, alias="Purchases conversion value (INR)")
    new_customers: int = Field(default=0, alias="New Customers")
