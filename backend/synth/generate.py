"""Synthetic data generator for Hayah Care.

Produces CSVs matching the column layout of the real exports Hayah Care will
eventually drop into ``data/raw/<source>/``. Every table is generated from a
single seed so a run is fully reproducible. The data is deliberately messy —
duplicate rows, blank phones, mixed date formats, a mid-range SKU rename — so
the Step 1 ingest adapters have something real to clean up. When actual
exports arrive, fix the adapter *and* this generator together so the two
never drift apart (see CLAUDE.md).

Usage:
    python -m backend.synth.generate --seed 42 --days 182
"""

from __future__ import annotations

import argparse
import csv
import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO_ROOT / "data" / "raw"

KERALA_CITIES = ["Kozhikode", "Kochi", "Thrissur", "Kannur", "Malappuram", "Kollam"]
OTHER_CITIES = [
    ("Bengaluru", "Karnataka"),
    ("Chennai", "Tamil Nadu"),
    ("Mumbai", "Maharashtra"),
    ("Delhi", "Delhi"),
    ("Hyderabad", "Telangana"),
    ("Coimbatore", "Tamil Nadu"),
    ("Pune", "Maharashtra"),
]
FIRST_NAMES = [
    "Aisha", "Aravind", "Divya", "Fathima", "Gopika", "Hari", "Irfan", "Jyothi",
    "Kavya", "Liya", "Muhsin", "Nandini", "Rahul", "Sana", "Vishnu", "Zara",
    "Anjali", "Basil", "Devika", "Nithin",
]
LAST_NAMES = [
    "Menon", "Nair", "Pillai", "Khan", "Iqbal", "Varma", "Thomas", "Joseph",
    "Kutty", "Rahman", "Das", "Kumar", "Shah", "Fernandez",
]

DISCOUNT_CODES = ["WELCOME10", "FEST20", "WELCOME10", "", "", "", "", ""]

SEARCH_QUERIES = [
    "healthy dry fruit mix", "trail mix online india", "nuts and seeds mix",
    "chukku kappi powder", "kerala dry ginger coffee", "supermix for breakfast",
    "protein snack mix india", "roasted nuts mix jar", "sugar free trail mix",
    "immunity booster powder kerala", "diabetic friendly snacks",
    "mom's supermix", "healthy snacks for kids", "nut mix for weight loss",
    "kappi podi online", "seeds mix for pregnancy", "hayah care",
    "energy mix nuts seeds", "kerala superfood mix", "no sugar snack jar",
]


@dataclass
class Product:
    sku: str
    shopify_title: str | None
    amazon_title: str | None
    asin: str | None
    price: float
    channels: tuple[str, ...]
    rename_from: str | None = None
    rename_sku_from: str | None = None
    rename_cutover_day: int | None = None


PRODUCTS = [
    Product(
        sku="NSS-400",
        shopify_title="Nuts & Seeds Supermix 400g",
        amazon_title="Hayah Care Nuts & Seeds Supermix, 400g Jar",
        asin="B0HAYA0001",
        price=999.0,
        channels=("shopify", "amazon"),
    ),
    Product(
        sku="MOM-400",
        shopify_title="Mom's Supermix 400g",
        amazon_title="Hayah Care Mom's Supermix, 400g Jar",
        asin="B0HAYA0002",
        price=999.0,
        channels=("shopify", "amazon"),
        rename_from="Mom's Mix 400g",
        rename_sku_from="MOM-MIX-400",
        rename_cutover_day=90,
    ),
    Product(
        sku="CK-2PK",
        shopify_title="Chukku Kappi Powder (2-Pack)",
        amazon_title=None,
        asin=None,
        price=349.0,
        channels=("shopify",),
    ),
    Product(
        sku="NSS-830",
        shopify_title=None,
        amazon_title="Hayah Care Nuts & Seeds Supermix, 830g Jar",
        asin="B0HAYA0003",
        price=1799.0,
        channels=("amazon",),
    ),
]

SHOPIFY_PRODUCTS = [p for p in PRODUCTS if "shopify" in p.channels]
AMAZON_PRODUCTS = [p for p in PRODUCTS if "amazon" in p.channels]


def shopify_title_sku(product: Product, order_day_offset: int) -> tuple[str, str]:
    """Return (Lineitem name, Lineitem sku) honoring the mid-range rename."""
    if product.rename_cutover_day is not None and order_day_offset < product.rename_cutover_day:
        return product.rename_from, product.rename_sku_from
    return product.shopify_title, product.sku


def messy_date(dt: datetime, rng: random.Random, variants: list[str] | None = None) -> str:
    fmt = rng.choice(variants or [
        "%Y-%m-%d %H:%M:%S +0530",
        "%d-%m-%Y",
        "%B %d, %Y",
        "%Y/%m/%d %H:%M",
        "%d/%m/%Y",
    ])
    return dt.strftime(fmt)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


@dataclass
class Customer:
    customer_id: int
    first_name: str
    last_name: str
    email: str
    phone: str | None
    city: str
    province: str
    country: str = "India"
    accepts_marketing: bool = True


def gen_customers(n: int, rng: random.Random) -> list[Customer]:
    customers = []
    seen_emails: set[str] = set()
    for i in range(1, n + 1):
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        base_email = f"{first.lower()}.{last.lower()}{i}@example.com"
        while base_email in seen_emails:
            base_email = f"{first.lower()}.{last.lower()}{i}{rng.randint(1,999)}@example.com"
        seen_emails.add(base_email)
        if rng.random() < 0.55:
            city, province = rng.choice(KERALA_CITIES), "Kerala"
        else:
            city, province = rng.choice(OTHER_CITIES)
        phone = None if rng.random() < 0.3 else f"9{rng.randint(100000000, 999999999)}"
        customers.append(
            Customer(
                customer_id=i,
                first_name=first,
                last_name=last,
                email=base_email,
                phone=phone,
                city=city,
                province=province,
                accepts_marketing=rng.random() < 0.6,
            )
        )
    return customers


@dataclass
class OrderEvent:
    order_seq: int
    day_offset: int
    dt: datetime
    channel: str
    customer: Customer
    items: list[tuple[Product, int]]
    discount_code: str
    is_refunded: bool
    financial_status: str


def gen_order_events(
    customers: list[Customer], start: date, days: int, rng: random.Random
) -> list[OrderEvent]:
    """Simulate order arrivals with growth, weekly seasonality, and repeat buyers."""
    events: list[OrderEvent] = []
    order_seq = 1000
    # each customer's order history, to model reorder gaps
    last_order_day: dict[int, int] = {}
    customer_first_sku: dict[int, str] = {}

    for day_offset in range(days):
        day = start + timedelta(days=day_offset)
        growth = 0.5 + 1.0 * (day_offset / days)  # ramps up over the window
        weekday_factor = 1.3 if day.weekday() in (5, 6) else 1.0
        expected = 1.6 * growth * weekday_factor
        n_orders_today = poisson(expected, rng)

        for _ in range(n_orders_today):
            channel = "shopify" if rng.random() < 0.62 else "amazon"
            # 35% chance of a repeat customer once we're > 30 days in
            repeat_pool = [
                cid for cid, last_day in last_order_day.items()
                if day_offset - last_day >= 14
            ]
            if day_offset > 30 and repeat_pool and rng.random() < 0.35:
                cid = rng.choice(repeat_pool)
                customer = customers[cid - 1]
            else:
                customer = rng.choice(customers)

            products = SHOPIFY_PRODUCTS if channel == "shopify" else AMAZON_PRODUCTS
            first_pick = rng.choice(products)
            items = [(first_pick, rng.choice([1, 1, 1, 2]))]
            # cross-sell: Chukku Kappi buyers sometimes add a 999 mix, and vice versa
            if channel == "shopify" and rng.random() < 0.22:
                other = rng.choice([p for p in products if p.sku != first_pick.sku])
                items.append((other, 1))

            discount_code = rng.choice(DISCOUNT_CODES) if channel == "shopify" else ""
            is_refunded = rng.random() < 0.04
            financial_status = "refunded" if is_refunded else "paid"

            hour = rng.randint(8, 23)
            dt = datetime(day.year, day.month, day.day, hour, rng.randint(0, 59), rng.randint(0, 59))

            events.append(
                OrderEvent(
                    order_seq=order_seq,
                    day_offset=day_offset,
                    dt=dt,
                    channel=channel,
                    customer=customer,
                    items=items,
                    discount_code=discount_code,
                    is_refunded=is_refunded,
                    financial_status=financial_status,
                )
            )
            last_order_day[customer.customer_id] = day_offset
            customer_first_sku.setdefault(customer.customer_id, first_pick.sku)
            order_seq += 1

    return events


def poisson(lam: float, rng: random.Random) -> int:
    """Small dependency-free Poisson sampler (Knuth's algorithm)."""
    import math
    l = math.exp(-lam)
    k = 0
    p = 1.0
    while True:
        k += 1
        p *= rng.random()
        if p <= l:
            return k - 1


def gen_shopify_orders_csv(events: list[OrderEvent], rng: random.Random) -> list[dict[str, Any]]:
    fieldnames = [
        "Name", "Email", "Financial Status", "Paid at", "Fulfillment Status",
        "Currency", "Subtotal", "Shipping", "Taxes", "Total", "Discount Code",
        "Discount Amount", "Created at", "Lineitem quantity", "Lineitem name",
        "Lineitem price", "Lineitem sku", "Cancelled at", "Payment Method",
        "Refunded Amount", "Id", "Tags", "Phone", "Shipping City", "Shipping Province",
    ]
    rows: list[dict[str, Any]] = []
    for ev in events:
        if ev.channel != "shopify":
            continue
        order_name = f"#{ev.order_seq}"
        subtotal = sum(p.price * qty for p, qty in ev.items)
        shipping = 0.0  # Hayah Care ships free — the leak the brief calls out
        discount_amt = round(subtotal * 0.10, 2) if ev.discount_code else 0.0
        taxes = round((subtotal - discount_amt) * 0.05, 2)
        total = round(subtotal - discount_amt + shipping + taxes, 2)
        created_str = messy_date(ev.dt, rng)
        paid_str = created_str if ev.financial_status == "paid" else ""

        for product, qty in ev.items:
            name, sku = shopify_title_sku(product, ev.day_offset)
            rows.append({
                "Name": order_name,
                "Email": ev.customer.email,
                "Financial Status": ev.financial_status,
                "Paid at": paid_str,
                "Fulfillment Status": rng.choice(["fulfilled", "fulfilled", "unfulfilled"]),
                "Currency": "INR",
                "Subtotal": subtotal,
                "Shipping": shipping,
                "Taxes": taxes,
                "Total": total,
                "Discount Code": ev.discount_code,
                "Discount Amount": discount_amt,
                "Created at": created_str,
                "Lineitem quantity": qty,
                "Lineitem name": name,
                "Lineitem price": product.price,
                "Lineitem sku": sku,
                "Cancelled at": "",
                "Payment Method": rng.choice(["Razorpay", "UPI", "Cash on Delivery"]),
                "Refunded Amount": total if ev.is_refunded else 0.0,
                "Id": ev.order_seq,
                "Tags": "",
                "Phone": ev.customer.phone or "",
                "Shipping City": ev.customer.city,
                "Shipping Province": ev.customer.province,
            })
        if ev.is_refunded:
            # a refund shows up as its own negative line, the way Shopify exports it
            product, qty = ev.items[0]
            name, sku = shopify_title_sku(product, ev.day_offset)
            rows.append({
                "Name": order_name,
                "Email": ev.customer.email,
                "Financial Status": ev.financial_status,
                "Paid at": paid_str,
                "Fulfillment Status": "restocked",
                "Currency": "INR",
                "Subtotal": -subtotal,
                "Shipping": 0.0,
                "Taxes": -taxes,
                "Total": -total,
                "Discount Code": "",
                "Discount Amount": 0.0,
                "Created at": messy_date(ev.dt + timedelta(days=rng.randint(1, 5)), rng),
                "Lineitem quantity": -qty,
                "Lineitem name": name,
                "Lineitem price": product.price,
                "Lineitem sku": sku,
                "Cancelled at": "",
                "Payment Method": "",
                "Refunded Amount": 0.0,
                "Id": ev.order_seq,
                "Tags": "refund",
                "Phone": ev.customer.phone or "",
                "Shipping City": ev.customer.city,
                "Shipping Province": ev.customer.province,
            })

    # accidental duplicate export rows — ~1.5% of rows get double-written
    dupes = rng.sample(rows, k=max(1, int(len(rows) * 0.015)))
    rows.extend(dict(r) for r in dupes)
    return fieldnames, rows


def gen_shopify_customers_csv(customers: list[Customer], events: list[OrderEvent]) -> tuple[list[str], list[dict]]:
    fieldnames = [
        "First Name", "Last Name", "Email", "Accepts Marketing", "City", "Province",
        "Country", "Zip", "Phone", "Total Spent", "Total Orders", "Id",
    ]
    spend: dict[int, float] = {}
    orders_ct: dict[int, int] = {}
    for ev in events:
        if ev.channel != "shopify":
            continue
        total = sum(p.price * qty for p, qty in ev.items)
        spend[ev.customer.customer_id] = spend.get(ev.customer.customer_id, 0.0) + total
        orders_ct[ev.customer.customer_id] = orders_ct.get(ev.customer.customer_id, 0) + 1

    rows = []
    for c in customers:
        if c.customer_id not in orders_ct:
            continue  # only customers who actually ordered on Shopify appear in this export
        rows.append({
            "First Name": c.first_name,
            "Last Name": c.last_name,
            "Email": c.email,
            "Accepts Marketing": "yes" if c.accepts_marketing else "no",
            "City": c.city,
            "Province": c.province,
            "Country": c.country,
            "Zip": f"6{'0' if c.province == 'Kerala' else '1'}{1000 + c.customer_id % 8999:04d}",
            "Phone": c.phone or "",
            "Total Spent": round(spend[c.customer_id], 2),
            "Total Orders": orders_ct[c.customer_id],
            "Id": c.customer_id,
        })
    return fieldnames, rows


def gen_sessions_daily(events: list[OrderEvent], start: date, days: int, rng: random.Random) -> tuple[list[str], list[dict]]:
    fieldnames = ["Date", "Sessions"]
    shopify_orders_by_day: dict[int, int] = {}
    for ev in events:
        if ev.channel == "shopify":
            shopify_orders_by_day[ev.day_offset] = shopify_orders_by_day.get(ev.day_offset, 0) + 1

    rows = []
    for day_offset in range(days):
        day = start + timedelta(days=day_offset)
        orders = shopify_orders_by_day.get(day_offset, 0)
        conv_rate = rng.uniform(0.012, 0.028)
        sessions = max(orders, int(orders / conv_rate) if conv_rate > 0 else 0)
        sessions += rng.randint(0, 15)  # organic browsing with no purchase
        rows.append({"Date": day.isoformat(), "Sessions": sessions})
    return fieldnames, rows


def gen_shopify_funnel_daily(
    events: list[OrderEvent], sessions_daily_rows: list[dict], rng: random.Random
) -> tuple[list[str], list[dict]]:
    """Shopify's own funnel report: sessions -> add to cart -> checkout ->
    purchase. Built from the same per-day session counts as sessions_by_day
    (so the two reports agree on sessions) and anchored to the *actual*
    per-day order count for completed checkout, then worked backwards
    through realistic drop-off ratios — otherwise "completed checkout" and
    the real order count drift apart with nothing tying them together."""
    shopify_orders_by_day: dict[int, int] = {}
    for ev in events:
        if ev.channel == "shopify":
            shopify_orders_by_day[ev.day_offset] = shopify_orders_by_day.get(ev.day_offset, 0) + 1

    fieldnames = ["Date", "Sessions", "Added to Cart", "Reached Checkout", "Completed Checkout"]
    rows = []
    for day_offset, row in enumerate(sessions_daily_rows):
        sessions = row["Sessions"]
        completed_checkout = shopify_orders_by_day.get(day_offset, 0)

        checkout_complete_rate = rng.uniform(0.55, 0.75)
        reached_checkout = max(
            completed_checkout, int(completed_checkout / checkout_complete_rate) if checkout_complete_rate else 0
        )
        cart_to_checkout_rate = rng.uniform(0.55, 0.75)
        added_to_cart = max(
            reached_checkout, int(reached_checkout / cart_to_checkout_rate) if cart_to_checkout_rate else 0
        )
        added_to_cart = min(added_to_cart, sessions)
        reached_checkout = min(reached_checkout, added_to_cart)
        completed_checkout = min(completed_checkout, reached_checkout)

        rows.append({
            "Date": row["Date"],
            "Sessions": sessions,
            "Added to Cart": added_to_cart,
            "Reached Checkout": reached_checkout,
            "Completed Checkout": completed_checkout,
        })
    return fieldnames, rows


REFERRERS = ["Direct", "Google (organic)", "Instagram", "Facebook Ads", "Google Ads", "Email", "Other"]
REFERRER_WEIGHTS = [0.22, 0.18, 0.15, 0.20, 0.10, 0.05, 0.10]


def gen_sessions_referrer(sessions_daily_rows: list[dict], rng: random.Random) -> tuple[list[str], list[dict]]:
    fieldnames = ["Date", "Referrer", "Sessions"]
    rows = []
    for row in sessions_daily_rows:
        total = row["Sessions"]
        remaining = total
        for i, (ref, w) in enumerate(zip(REFERRERS, REFERRER_WEIGHTS)):
            if i == len(REFERRERS) - 1:
                count = remaining
            else:
                count = int(total * w * rng.uniform(0.7, 1.3))
                count = min(count, remaining)
            remaining -= count
            if count > 0:
                rows.append({"Date": row["Date"], "Referrer": ref, "Sessions": count})
    return fieldnames, rows


def gen_abandoned_checkouts(customers: list[Customer], start: date, days: int, rng: random.Random) -> tuple[list[str], list[dict]]:
    fieldnames = ["Checkout ID", "Created at", "Email", "Phone", "Total", "Currency", "Items in Cart", "Recovered"]
    rows = []
    checkout_id = 5000
    for day_offset in range(days):
        day = start + timedelta(days=day_offset)
        n = poisson(1.1, rng)
        for _ in range(n):
            customer = rng.choice(customers)
            product = rng.choice(SHOPIFY_PRODUCTS)
            qty = rng.choice([1, 1, 2])
            dt = datetime(day.year, day.month, day.day, rng.randint(8, 23), rng.randint(0, 59))
            rows.append({
                "Checkout ID": checkout_id,
                "Created at": messy_date(dt, rng),
                "Email": customer.email,
                "Phone": customer.phone or "",
                "Total": round(product.price * qty, 2),
                "Currency": "INR",
                "Items in Cart": qty,
                "Recovered": "yes" if rng.random() < 0.08 else "no",
            })
            checkout_id += 1
    return fieldnames, rows


def gen_amazon_detail_page_sales_traffic(start: date, days: int, rng: random.Random) -> tuple[list[str], list[dict]]:
    fieldnames = [
        "(Child) ASIN", "Title", "Sessions - Total", "Page Views - Total",
        "Featured Offer (Buy Box) Percentage", "Units Ordered",
        "Unit Session Percentage", "Ordered Product Sales", "Date",
    ]
    rows = []
    for day_offset in range(days):
        day = start + timedelta(days=day_offset)
        for p in AMAZON_PRODUCTS:
            sessions = max(0, int(rng.gauss(18, 8)))
            page_views = int(sessions * rng.uniform(1.1, 1.6))
            unit_session_pct = rng.uniform(0.03, 0.12)
            units = poisson(sessions * unit_session_pct, rng)
            rows.append({
                "(Child) ASIN": p.asin,
                "Title": p.amazon_title,
                "Sessions - Total": sessions,
                "Page Views - Total": page_views,
                "Featured Offer (Buy Box) Percentage": round(rng.uniform(0.75, 1.0), 3),
                "Units Ordered": units,
                "Unit Session Percentage": round(unit_session_pct, 4),
                "Ordered Product Sales": round(units * p.price, 2),
                "Date": day.isoformat(),
            })
    return fieldnames, rows


def gen_search_query_performance(start: date, days: int, rng: random.Random) -> tuple[list[str], list[dict]]:
    fieldnames = [
        "Search Query", "Week Start Date", "Impressions: Total Count",
        "Clicks: Total Count", "Click Rate %", "Cart Adds: Total Count",
        "Purchases: Total Count", "Purchase Rate %",
    ]
    rows = []
    # assign each query a fixed "problem archetype" so Step 5 has real signal to rank
    archetypes = {}
    for q in SEARCH_QUERIES:
        archetypes[q] = rng.choice(["healthy", "healthy", "listing_problem", "price_problem"])

    for week_start_offset in range(0, days, 7):
        day = start + timedelta(days=week_start_offset)
        for q in SEARCH_QUERIES:
            impressions = int(rng.gauss(800, 300))
            impressions = max(50, impressions)
            archetype = archetypes[q]
            if archetype == "listing_problem":
                click_rate = rng.uniform(0.005, 0.02)  # impressions but few clicks
            else:
                click_rate = rng.uniform(0.03, 0.09)
            clicks = int(impressions * click_rate)
            cart_adds = int(clicks * rng.uniform(0.2, 0.5))
            if archetype == "price_problem":
                purchase_rate_of_clicks = rng.uniform(0.01, 0.05)  # clicks but few purchases
            else:
                purchase_rate_of_clicks = rng.uniform(0.08, 0.25)
            purchases = int(clicks * purchase_rate_of_clicks)
            rows.append({
                "Search Query": q,
                "Week Start Date": day.isoformat(),
                "Impressions: Total Count": impressions,
                "Clicks: Total Count": clicks,
                "Click Rate %": round(click_rate * 100, 2),
                "Cart Adds: Total Count": cart_adds,
                "Purchases: Total Count": purchases,
                "Purchase Rate %": round((purchases / clicks * 100) if clicks else 0.0, 2),
            })
    return fieldnames, rows


CAMPAIGNS = ["Hayah - Supermix - Auto", "Hayah - Supermix - Exact", "Hayah - Chukku Kappi - Broad"]


def gen_sp_campaign_report(start: date, days: int, rng: random.Random) -> tuple[list[str], list[dict]]:
    fieldnames = [
        "Date", "Campaign Name", "Campaign Status", "Impressions", "Clicks",
        "CTR", "Spend", "CPC", "Orders", "Sales", "ACOS",
    ]
    rows = []
    for day_offset in range(days):
        day = start + timedelta(days=day_offset)
        for camp in CAMPAIGNS:
            impressions = max(0, int(rng.gauss(1200, 400)))
            ctr = rng.uniform(0.003, 0.012)
            clicks = int(impressions * ctr)
            cpc = rng.uniform(8, 22)
            spend = round(clicks * cpc, 2)
            orders = poisson(clicks * rng.uniform(0.02, 0.08), rng)
            sales = round(orders * rng.choice([999.0, 1799.0]), 2)
            acos = round((spend / sales * 100) if sales else 0.0, 2)
            rows.append({
                "Date": day.isoformat(),
                "Campaign Name": camp,
                "Campaign Status": "enabled",
                "Impressions": impressions,
                "Clicks": clicks,
                "CTR": round(ctr * 100, 3),
                "Spend": spend,
                "CPC": round(cpc, 2),
                "Orders": orders,
                "Sales": sales,
                "ACOS": acos,
            })
    return fieldnames, rows


def gen_sp_search_term_report(start: date, days: int, rng: random.Random) -> tuple[list[str], list[dict]]:
    fieldnames = [
        "Date", "Campaign Name", "Ad Group Name", "Match Type", "Customer Search Term",
        "Impressions", "Clicks", "Spend", "7 Day Total Sales", "7 Day Total Orders (#)",
    ]
    rows = []
    for week_start_offset in range(0, days, 7):
        day = start + timedelta(days=week_start_offset)
        for camp in CAMPAIGNS:
            for q in rng.sample(SEARCH_QUERIES, k=6):
                impressions = max(0, int(rng.gauss(150, 60)))
                clicks = int(impressions * rng.uniform(0.01, 0.08))
                spend = round(clicks * rng.uniform(8, 22), 2)
                orders = poisson(clicks * 0.05, rng)
                sales = round(orders * rng.choice([999.0, 349.0]), 2)
                rows.append({
                    "Date": day.isoformat(),
                    "Campaign Name": camp,
                    "Ad Group Name": f"{camp} - AdGroup 1",
                    "Match Type": rng.choice(["exact", "phrase", "broad"]),
                    "Customer Search Term": q,
                    "Impressions": impressions,
                    "Clicks": clicks,
                    "Spend": spend,
                    "7 Day Total Sales": sales,
                    "7 Day Total Orders (#)": orders,
                })
    return fieldnames, rows


def gen_amazon_returns(events: list[OrderEvent], rng: random.Random) -> tuple[list[str], list[dict]]:
    fieldnames = ["Return Date", "Order ID", "SKU", "ASIN", "Return Reason", "Return Quantity", "Refund Amount"]
    reasons = ["Item defective", "No longer needed", "Wrong item sent", "Better price found", "Product damaged in transit"]
    rows = []
    for ev in events:
        if ev.channel != "amazon":
            continue
        if rng.random() < 0.05:
            product, qty = ev.items[0]
            return_day = ev.dt + timedelta(days=rng.randint(2, 14))
            rows.append({
                "Return Date": return_day.date().isoformat(),
                "Order ID": f"AMZ-{ev.order_seq}",
                "SKU": product.sku,
                "ASIN": product.asin,
                "Return Reason": rng.choice(reasons),
                "Return Quantity": qty,
                "Refund Amount": round(product.price * qty, 2),
            })
    return fieldnames, rows


META_CAMPAIGNS = ["Hayah - Prospecting - Supermix", "Hayah - Retargeting - All"]
META_ADSETS = {
    "Hayah - Prospecting - Supermix": ["Lookalike 1%", "Interest - Healthy Eating", "Broad 25-45"],
    "Hayah - Retargeting - All": ["Cart Abandoners 30d", "Website Visitors 180d"],
}


def gen_meta_ads_insights(start: date, days: int, rng: random.Random) -> tuple[list[str], list[dict]]:
    fieldnames = [
        "Reporting starts", "Campaign name", "Ad set name", "Amount spent (INR)",
        "Impressions", "Reach", "Frequency", "CPM (cost per 1,000 impressions) (INR)",
        "Clicks (all)", "CTR (all)", "Purchases", "Purchases conversion value (INR)",
    ]
    rows = []
    # give each adset a stable "peak CTR" so fatigue can be computed from its own history
    peak_ctr = {}
    for camp, adsets in META_ADSETS.items():
        for a in adsets:
            peak_ctr[a] = rng.uniform(0.01, 0.025)

    for day_offset in range(days):
        day = start + timedelta(days=day_offset)
        for camp, adsets in META_ADSETS.items():
            for adset in adsets:
                # scaled so total spend lands around 15-20% of Shopify revenue —
                # a small brand's real budget, not a number that bankrupts every order
                spend = round(max(0.0, rng.gauss(35, 15)), 2)
                cpm = rng.uniform(180, 420)
                impressions = int(spend / cpm * 1000) if cpm else 0
                # frequency creeps up in the back half of the window for one adset
                fatigue = adset == "Broad 25-45" and day_offset > days * 0.7
                frequency = round(rng.uniform(2.7, 3.4) if fatigue else rng.uniform(1.1, 2.2), 2)
                ctr = peak_ctr[adset] * (rng.uniform(0.5, 0.65) if fatigue else rng.uniform(0.85, 1.1))
                clicks = int(impressions * ctr)
                reach = int(impressions / max(frequency, 1.0))
                purchase_rate = rng.uniform(0.01, 0.05) if "Retargeting" in camp else rng.uniform(0.005, 0.02)
                purchases = poisson(clicks * purchase_rate, rng)
                value = round(purchases * rng.choice([999.0, 349.0, 1799.0]), 2)
                rows.append({
                    "Reporting starts": day.isoformat(),
                    "Campaign name": camp,
                    "Ad set name": adset,
                    "Amount spent (INR)": spend,
                    "Impressions": impressions,
                    "Reach": reach,
                    "Frequency": frequency,
                    "CPM (cost per 1,000 impressions) (INR)": round(cpm, 2),
                    "Clicks (all)": clicks,
                    "CTR (all)": round(ctr * 100, 3),
                    "Purchases": purchases,
                    "Purchases conversion value (INR)": value,
                })
    return fieldnames, rows


def generate(seed: int, days: int, end_date: date, out_dir: Path, n_customers: int) -> dict[str, int]:
    rng = random.Random(seed)
    start = end_date - timedelta(days=days)

    customers = gen_customers(n_customers, rng)
    events = gen_order_events(customers, start, days, rng)

    counts = {}

    fn, rows = gen_shopify_orders_csv(events, rng)
    write_csv(out_dir / "shopify_orders" / "orders_export.csv", fn, rows)
    counts["shopify_orders"] = len(rows)

    fn, rows = gen_shopify_customers_csv(customers, events)
    write_csv(out_dir / "shopify_customers" / "customers_export.csv", fn, rows)
    counts["shopify_customers"] = len(rows)

    fn, sessions_daily_rows = gen_sessions_daily(events, start, days, rng)
    write_csv(out_dir / "shopify_sessions_daily" / "sessions_by_day.csv", fn, sessions_daily_rows)
    counts["shopify_sessions_daily"] = len(sessions_daily_rows)

    fn, rows = gen_shopify_funnel_daily(events, sessions_daily_rows, rng)
    write_csv(out_dir / "shopify_funnel_daily" / "funnel_by_day.csv", fn, rows)
    counts["shopify_funnel_daily"] = len(rows)

    fn, rows = gen_sessions_referrer(sessions_daily_rows, rng)
    write_csv(out_dir / "shopify_sessions_referrer" / "sessions_by_referrer.csv", fn, rows)
    counts["shopify_sessions_referrer"] = len(rows)

    fn, rows = gen_abandoned_checkouts(customers, start, days, rng)
    write_csv(out_dir / "shopify_abandoned_checkouts" / "abandoned_checkouts.csv", fn, rows)
    counts["shopify_abandoned_checkouts"] = len(rows)

    fn, rows = gen_amazon_detail_page_sales_traffic(start, days, rng)
    write_csv(out_dir / "amazon_detail_page_sales_traffic" / "detail_page_sales_traffic.csv", fn, rows)
    counts["amazon_detail_page_sales_traffic"] = len(rows)

    fn, rows = gen_search_query_performance(start, days, rng)
    write_csv(out_dir / "amazon_search_query_performance" / "search_query_performance.csv", fn, rows)
    counts["amazon_search_query_performance"] = len(rows)

    fn, rows = gen_sp_campaign_report(start, days, rng)
    write_csv(out_dir / "amazon_sp_campaign_report" / "sp_campaign_report.csv", fn, rows)
    counts["amazon_sp_campaign_report"] = len(rows)

    fn, rows = gen_sp_search_term_report(start, days, rng)
    write_csv(out_dir / "amazon_sp_search_term_report" / "sp_search_term_report.csv", fn, rows)
    counts["amazon_sp_search_term_report"] = len(rows)

    fn, rows = gen_amazon_returns(events, rng)
    write_csv(out_dir / "amazon_returns" / "amazon_returns.csv", fn, rows)
    counts["amazon_returns"] = len(rows)

    fn, rows = gen_meta_ads_insights(start, days, rng)
    write_csv(out_dir / "meta_ads_insights" / "meta_ads_insights.csv", fn, rows)
    counts["meta_ads_insights"] = len(rows)

    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--days", type=int, default=182)
    parser.add_argument("--end-date", type=str, default=date.today().isoformat())
    parser.add_argument("--out-dir", type=str, default=str(DEFAULT_OUT))
    parser.add_argument("--n-customers", type=int, default=260)
    args = parser.parse_args()

    end_date = date.fromisoformat(args.end_date)
    counts = generate(args.seed, args.days, end_date, Path(args.out_dir), args.n_customers)

    print(f"Generated synthetic data (seed={args.seed}, days={args.days}, end_date={end_date}) into {args.out_dir}")
    for source, n in counts.items():
        print(f"  {source}: {n} rows")


if __name__ == "__main__":
    main()
