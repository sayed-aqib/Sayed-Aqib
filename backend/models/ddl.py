"""DuckDB schema for the Hayah Care warehouse.

Every table carries a ``source_file`` column and enough of a natural-key
primary key that re-running the same export file upserts in place instead of
duplicating rows (see backend/ingest/common.py:upsert_rows). ``ingest_issues``
is the audit trail: every adapter logs what it rejected outright and what it
kept but flagged (e.g. an unmapped SKU), and why.
"""

from __future__ import annotations

import duckdb

DDL_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS products (
        product_id  VARCHAR PRIMARY KEY,
        name        VARCHAR NOT NULL,
        channels    VARCHAR NOT NULL,
        list_price  DOUBLE NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS customers (
        customer_id       VARCHAR PRIMARY KEY,
        channel           VARCHAR NOT NULL,
        shopify_numeric_id BIGINT,
        email             VARCHAR,
        first_name        VARCHAR,
        last_name         VARCHAR,
        phone             VARCHAR,
        city              VARCHAR,
        province          VARCHAR,
        country           VARCHAR,
        accepts_marketing BOOLEAN,
        total_spent       DOUBLE,
        total_orders      INTEGER,
        source_file       VARCHAR NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS orders (
        order_id           VARCHAR PRIMARY KEY,
        channel            VARCHAR NOT NULL,
        customer_id        VARCHAR,
        order_name         VARCHAR,
        created_at         TIMESTAMP NOT NULL,
        paid_at            TIMESTAMP,
        financial_status   VARCHAR,
        fulfillment_status VARCHAR,
        currency           VARCHAR,
        subtotal           DOUBLE,
        shipping           DOUBLE,
        taxes              DOUBLE,
        discount_code      VARCHAR,
        discount_amount    DOUBLE,
        total              DOUBLE,
        refunded_amount    DOUBLE,
        payment_method     VARCHAR,
        shipping_city      VARCHAR,
        shipping_province  VARCHAR,
        source_file        VARCHAR NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS order_items (
        order_id        VARCHAR NOT NULL,
        line_seq        INTEGER NOT NULL,
        product_id      VARCHAR,
        raw_sku         VARCHAR,
        raw_title       VARCHAR,
        quantity        INTEGER NOT NULL,
        unit_price      DOUBLE NOT NULL,
        line_amount     DOUBLE NOT NULL,
        is_refund_line  BOOLEAN NOT NULL DEFAULT FALSE,
        source_file     VARCHAR NOT NULL,
        PRIMARY KEY (order_id, line_seq)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sessions_daily (
        date         DATE NOT NULL,
        referrer     VARCHAR NOT NULL DEFAULT '(all)',
        sessions     INTEGER NOT NULL,
        source_file  VARCHAR NOT NULL,
        PRIMARY KEY (date, referrer)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS shopify_funnel_daily (
        date                DATE PRIMARY KEY,
        sessions            INTEGER,
        home_page_views     INTEGER,
        product_page_views  INTEGER,
        added_to_cart       INTEGER,
        reached_checkout    INTEGER,
        completed_checkout  INTEGER,
        source_file         VARCHAR NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS abandoned_checkouts (
        checkout_id    VARCHAR PRIMARY KEY,
        created_at     TIMESTAMP NOT NULL,
        email          VARCHAR,
        phone          VARCHAR,
        total          DOUBLE,
        currency       VARCHAR,
        items_in_cart  INTEGER,
        recovered      BOOLEAN,
        source_file    VARCHAR NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS amazon_product_traffic_daily (
        date                    DATE NOT NULL,
        raw_asin                VARCHAR NOT NULL,
        product_id              VARCHAR,
        sessions                INTEGER,
        page_views              INTEGER,
        buybox_pct              DOUBLE,
        units_ordered           INTEGER,
        unit_session_pct        DOUBLE,
        ordered_product_sales   DOUBLE,
        source_file             VARCHAR NOT NULL,
        PRIMARY KEY (date, raw_asin)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS flipkart_product_traffic_daily (
        date                    DATE NOT NULL,
        raw_fsn                 VARCHAR NOT NULL,
        product_id              VARCHAR,
        sessions                INTEGER,
        units_ordered           INTEGER,
        ordered_product_sales   DOUBLE,
        source_file             VARCHAR NOT NULL,
        PRIMARY KEY (date, raw_fsn)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS search_query_weekly (
        week_start          DATE NOT NULL,
        search_query        VARCHAR NOT NULL,
        impressions          INTEGER,
        clicks                INTEGER,
        click_rate_pct        DOUBLE,
        cart_adds             INTEGER,
        purchases             INTEGER,
        purchase_rate_pct     DOUBLE,
        source_file           VARCHAR NOT NULL,
        PRIMARY KEY (week_start, search_query)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ad_spend_daily (
        date           DATE NOT NULL,
        platform       VARCHAR NOT NULL,
        campaign_name  VARCHAR NOT NULL,
        adset_name     VARCHAR NOT NULL DEFAULT '(campaign level)',
        impressions    INTEGER,
        clicks         INTEGER,
        spend          DOUBLE,
        purchases      INTEGER,
        revenue        DOUBLE,
        ctr_pct        DOUBLE,
        cpc            DOUBLE,
        cpm            DOUBLE,
        frequency      DOUBLE,
        reach          INTEGER,
        acos_pct       DOUBLE,
        new_customers  INTEGER,
        source_file    VARCHAR NOT NULL,
        PRIMARY KEY (date, platform, campaign_name, adset_name)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ad_search_terms_weekly (
        week_start      DATE NOT NULL,
        platform         VARCHAR NOT NULL DEFAULT 'amazon',
        campaign_name    VARCHAR NOT NULL,
        ad_group_name    VARCHAR NOT NULL,
        match_type       VARCHAR,
        search_term      VARCHAR NOT NULL,
        impressions      INTEGER,
        clicks           INTEGER,
        spend            DOUBLE,
        sales            DOUBLE,
        orders           INTEGER,
        source_file      VARCHAR NOT NULL,
        PRIMARY KEY (week_start, campaign_name, ad_group_name, search_term)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS returns (
        return_id      VARCHAR PRIMARY KEY,
        platform       VARCHAR NOT NULL DEFAULT 'amazon',
        return_date    DATE NOT NULL,
        order_id       VARCHAR,
        product_id     VARCHAR,
        raw_sku        VARCHAR,
        reason         VARCHAR,
        quantity       INTEGER,
        refund_amount  DOUBLE,
        source_file    VARCHAR NOT NULL
    )
    """,
    "CREATE SEQUENCE IF NOT EXISTS ingest_issues_seq START 1",
    """
    CREATE TABLE IF NOT EXISTS ingest_issues (
        issue_id      BIGINT PRIMARY KEY DEFAULT nextval('ingest_issues_seq'),
        source        VARCHAR NOT NULL,
        file          VARCHAR NOT NULL,
        severity      VARCHAR NOT NULL,
        row_number    INTEGER,
        reason        VARCHAR NOT NULL,
        raw_row       VARCHAR,
        ingested_at   TIMESTAMP NOT NULL DEFAULT current_timestamp
    )
    """,
]


def init_db(con: duckdb.DuckDBPyConnection) -> None:
    for stmt in DDL_STATEMENTS:
        con.execute(stmt)


def connect(db_path: str) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(db_path)
    init_db(con)
    return con
