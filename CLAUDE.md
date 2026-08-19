# Hayah Care — Growth Analytics Dashboard

## Who this is for

Hayah Care is a small D2C food brand in Kozhikode, Kerala, roughly six months into selling. Three SKUs:

| SKU | Channel | Price |
|---|---|---|
| Nuts & Seeds Supermix 400g | Shopify + Amazon | ₹999 |
| Mom's Supermix 400g | Shopify + Amazon | ₹999 |
| Chukku Kappi Powder (2 x 150g) | Shopify | ₹349 |

An 830g Supermix also sells on Amazon. The founder is not an analyst. Every screen has to answer a question she would actually ask out loud, in words she already uses.

Build a dashboard that answers four questions: **where does the money actually go, where do customers drop off, do they come back, and how should we spend on Meta ads.**

## Hard constraints — read these before writing code

1. **The data does not exist yet.** CSV exports arrive over the coming weeks. Build against a synthetic data generator first (see below). Every module must run end to end on fake data on day one.
2. **Order volume is small** — expect hundreds, not thousands. No forecasting models, no churn prediction, no clustering. They will fit noise and the founder will trust a number that means nothing. Descriptive analytics done rigorously beats a model here. If a metric is computed on fewer than 30 orders or 3 conversions, the UI says so on the face of the number.
3. **Costs are unknown until she tells us.** COGS, packaging, shipping, and fees all live in an editable config, never hardcoded in a metric function.
4. No customer PII in the repo, no real CSVs committed, secrets in `.env` only.

## Stack

- **Backend:** Python 3.11, FastAPI, DuckDB (single file, `data/warehouse.duckdb`), pandas, Pydantic v2, pytest.
- **Frontend:** Vite + React + TypeScript, Tailwind, Recharts, TanStack Query.
- **No auth for v1** — runs locally. Add a single shared password before it goes on a server.

```
backend/
  ingest/        one adapter per source file → normalized table
  models/        Pydantic schemas + DuckDB DDL
  metrics/       pure functions, dataframe in → dataframe out, unit tested
  api/           FastAPI routers, thin — they call metrics, nothing more
  config/        costs.yaml, fees.yaml, meta_rules.yaml
  synth/         synthetic data generator
frontend/src/
  pages/         Overview, UnitEconomics, Funnel, Retention, Keywords, MetaAds
  components/
  lib/api.ts
data/raw/<source>/    CSV drop zone, gitignored
```

**Keep metric logic out of the API layer and out of React.** Every number rendered in the browser is computed by a tested function in `metrics/`. This is the thing that most often goes wrong in dashboards like this — the same metric ends up defined three different ways in three places.

## Build order

Do these in sequence. Get each one working end to end — generator → ingest → metric → endpoint → screen — before starting the next. Do not scaffold all six modules at once.

### Step 0 — Synthetic generator

`backend/synth/generate.py` produces realistic CSVs matching the exact column names of each real export listed below. Make it messy on purpose: duplicate order rows, blank phone numbers, refunds as negative lines, dates in mixed formats, a few orders with a discount code, one SKU renamed halfway through. Seeded so runs are reproducible. When real files land, they drop into the same folder and the same adapters read them.

### Step 1 — Ingest and warehouse

Adapters for each source. Every adapter validates against a Pydantic schema, logs rows it rejected and why, and is idempotent — re-running the same file must not duplicate rows.

Sources: Shopify orders, Shopify customers, Shopify sessions by day and by referrer, Shopify abandoned checkouts, Amazon Detail Page Sales & Traffic by Child Item, Amazon Search Query Performance, Amazon Sponsored Products campaign report, Amazon Sponsored Products search term report, Amazon returns, Meta Ads insights export (campaign / adset / day).

Normalized tables: `orders`, `order_items`, `customers`, `products`, `sessions_daily`, `ad_spend_daily`, `search_query_weekly`, `returns`.

Build a SKU mapping table. Amazon ASINs, Shopify variant IDs, and whatever the founder calls things in a spreadsheet all have to resolve to one product ID. Assume they will not match.

### Step 2 — Unit economics

The headline module. Per order and per SKU:

```
contribution margin = net revenue
                    − COGS
                    − packaging
                    − shipping borne by brand
                    − channel fees (Amazon referral, FBA, or payment gateway)
                    − returns provision
                    − allocated ad spend
```

Free shipping on a 400g jar at ₹999 is a real leak — surface shipping as its own line, in rupees and as a percentage of revenue, not buried in an "other costs" bucket. Show contribution margin per channel side by side. Amazon and Shopify have completely different cost structures and she is probably treating them as one business.

Costs come from `config/costs.yaml`, editable in the UI, versioned with an effective date so historical months don't silently change when a price does.

### Step 3 — Funnel

Two funnels, never merged into one number. Shopify: sessions → add to cart → checkout started → purchase, with drop-off percentage at each step. Amazon: sessions → unit session percentage → units, by child ASIN. Add referrer breakdown for Shopify sessions so paid and organic traffic are separable.

### Step 4 — Retention

For a 400g consumable this is the whole business.

- Repeat purchase rate overall and by first SKU bought
- Days between first and second order — median and distribution
- Monthly cohort table, orders per cohort over time
- Does Chukku Kappi at ₹349 pull people into the ₹999 mixes? Show the cross-sell path explicitly.

The reorder gap is the number that tells her whether a subscription makes sense. Make it prominent.

### Step 5 — Amazon keywords

From Search Query Performance: impression share versus conversion share per query. Rank queries where they get impressions but few clicks (listing or image problem) separately from queries with clicks but few purchases (price or review problem). These are different fixes and the table should say which one it is.

### Step 6 — Meta ads budget

Detailed below. Build last — it depends on contribution margin from Step 2.

## Meta ads budget module

This module decides how much to spend and where. It must be **advisory** — it recommends, she approves, nothing is ever pushed to Meta automatically.

**Anchor everything to break-even ROAS, not a target ROAS pulled from a blog post.**

```
breakeven ROAS = 1 / contribution margin ratio
allowable CPA  = contribution margin per order (in rupees)
```

If contribution margin is 40%, break-even ROAS is 2.5. Every adset gets judged against that line, and the line moves when her costs move. Show it as a horizontal marker on every ROAS chart.

**Metrics per campaign and per adset, rolling 7 and 28 day:** spend, purchases, revenue, ROAS, CPA versus allowable CPA, CPM, CTR, frequency, and new-customer share of purchases. Track blended MER (total revenue ÷ total ad spend) at the account level alongside platform-reported ROAS — Meta over-attributes, and MER is the honest number.

**Budget recommendations — rules, in `config/meta_rules.yaml`, not a model:**

| Condition (7-day window) | Recommendation |
|---|---|
| ROAS ≥ 1.2 × break-even, spend stable | Scale budget +20% |
| ROAS within ±20% of break-even | Hold |
| ROAS < break-even with ≥ 3 purchases | Cut 30% |
| ROAS < 0.5 × break-even with ≥ 5 purchases | Pause, flag for review |
| Fewer than 3 purchases or under ₹3,000 spent | Insufficient data — hold, show why |

Guardrails, enforced in code: no budget change greater than 25% in one step, no adset touched more than once every 3 days (Meta's learning phase resets otherwise), and no recommendation at all on an adset live under 7 days.

**Creative fatigue flag:** frequency above 2.5 with CTR down more than 30% from its own 7-day peak. Label it "creative is tiring, not failing" — it's a different action from cutting budget.

Every recommendation card shows the rule that fired, the numbers behind it, and a confidence label driven purely by sample size. Never show a recommendation without its reasoning; she needs to be able to disagree with it.

## Design direction

Data-dense and quiet. Analyst tool, not a marketing page — she will read it on a laptop while doing three other things.

Do not use the brand's packaging palette for the interface. Deep green and jaggery gold belong on a jar, and against charts they cause exactly the confusion you want to avoid: green means "good" in a dashboard, and if the whole chrome is green nothing reads as good. Instead:

- **Surface** `#FAFAF8`, **panel** `#FFFFFF`, **border** `#E4E3DE`
- **Ink** `#1A1A17`, **muted ink** `#6E6E66`
- **Semantic only:** positive `#2D6A4F`, negative `#B3402E`, caution `#B58A00`
- Brand green `#1F4032` appears in the header rule and nowhere else

Type: one grotesk for the interface, tabular lining figures everywhere a number appears — misaligned decimal columns make a dashboard feel untrustworthy before anyone reads a value. Size the numbers, not the labels.

Chart rules: no gridlines heavier than the data, no gradients under area charts, no pie charts, no dual axes ever. Currency always as ₹ with Indian digit grouping (₹1,00,000, not ₹100,000) — she will notice immediately if this is wrong.

**Every card carries its definition.** A small info affordance showing exactly how the number is computed, in one sentence, in her words. "Contribution margin: what's left from each order after we pay for the product, the jar, shipping, platform fees and ads." This is the difference between a dashboard she uses and one she opens twice.

Empty states are instructions, not decoration: name the export that's missing and where to drop it.

## Working agreement

Small commits, conventional commit messages. Write the test before the metric — the metrics layer is where correctness matters and where a silent error survives longest. When a real CSV arrives and its columns differ from the synthetic schema, fix the adapter and the generator together so they never drift apart.

Ask me before adding any dependency beyond the stack above.
