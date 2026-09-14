# Retail Promotion & Profitability Analytics

Analyzes retail transaction data to answer:
1. Promo lift — do promotions drive more units/revenue per day?
2. Margin erosion — how much margin do promotions cost?
3. Promo ranking — which SKUs run profitable promotions vs. losing ones?
4. Price elasticity — how price-sensitive is demand, per SKU?

## Project structure

\`\`\`
retail-promo-analytics/
├── src/
│   ├── data/
│   │   ├── loader.py       # read raw CSVs from data/raw/
│   │   └── cleaning.py     # dedup, validity flags, canonical recompute
│   ├── features/           # (next: joins + is_promo derivation)
│   ├── analysis/           # (next: lift, erosion, ranking, elasticity)
│   └── utils/               # (next: parallel processing helper)
├── tests/
├── data/raw/                # your 5 source CSVs go here (gitignored)
└── outputs/                 # generated results (gitignored)
\`\`\`

## Setup

\`\`\`powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
\`\`\`

## Data expectations

Place these five CSVs in `data/raw/` (star schema):

| File | Grain | Key columns |
|---|---|---|
| `dim_customer.csv` | 1 row / customer | `customer_id`, `customer_segment`, `gender`, `age`, `city` |
| `dim_date.csv` | 1 row / calendar date | `date_key`, `date`, `year`, `quarter`, `month`, `week` |
| `dim_product.csv` | 1 row / SKU | `product_id`, `category`, `unit_cost`, `selling_price` |
| `dim_store.csv` | 1 row / store | `store_id`, `region`, `store_type` |
| `fact_sales.csv` | 1 row / transaction line | `transaction_id`, `transaction_date`, `customer_id`, `product_id`, `store_id`, `quantity`, `unit_price`, `discount_amount`, `unit_cost` |

There's no explicit `promo_flag` — a transaction counts as **promoted** if `discount_amount > 0` (defined in `src/features`, coming next).

## Data quality handling

Real POS data has issues. We handle them explicitly rather than silently:

| Issue | Handling |
|---|---|
| Duplicate `transaction_id` | Deduplicated (keep first) |
| Bad `product_id`/`store_id` FK, zero quantity, non-positive price, date outside calendar | **Kept**, flagged `is_valid=False` with a reason; excluded only from aggregates |
| Negative quantity | Treated as a **return** (`is_return=True`), not a data error — kept valid, handled separately |
| `customer_id` present but not in `dim_customer` | **Kept**, flagged `has_valid_customer=False` (separate from `is_valid` — a bad customer link doesn't invalidate revenue/margin math, only customer-level cuts) |
| Provided `gross_sales`/`net_sales`/`profit_amount`/`gross_margin_pct` | **Recomputed** from base fields as canonical; disagreements flagged `qa_mismatch=True` |

Current QA results on this dataset (120,680 raw rows):

| Metric | Value |
|---|---|
| Duplicate rows removed | 680 |
| Invalid rows (excluded from aggregates) | 847 |
| Valid rows | 119,153 |
| Return rows (kept, analyzed separately) | 296 |
| Financial field mismatches (source vs. recomputed) | 495–1,087 depending on field |

## Analyses

**Promo lift** (`src/analysis/promo_lift.py`) — compares average daily units/revenue
during promo vs. non-promo periods, per SKU or category.

⚠️ **Known limitation, found during Step 8:** category-level results are
inflated by an aggregation artifact — since many SKUs share a category,
almost every calendar day contains a mix of promo and non-promo
transactions from *different* SKUs, so the "promo total" and "non-promo
total" aren't comparing the same products. **SKU-level results don't have
this problem** (a single SKU's day is almost always purely one regime or
the other) and are the trustworthy numbers — see promo ranking below.

At the SKU level: 88.6% of SKUs (443/500) showed *negative* revenue during
their promotional periods versus their own non-promotional baseline; only
11.2% (56/500) showed positive lift. This contradicts the (unreliable)
category-level average, which showed positive lift for every category.

**Margin erosion** (`src/analysis/margin_erosion.py`) — compares average gross
margin % and net incremental profit during promo vs. non-promo periods, per
SKU or category. This analysis is unaffected by the category-pooling issue
above, since it compares each group against its own non-promo baseline
regardless of granularity.

**Central finding:** every category shows margin erosion of 7.3–8.2 points,
and every category is net *unprofitable* during promotions
(`promo_profitable=False`) — the extra volume from Step 6's lift never
makes up for the margin given away. Total impact: ~20.2M SAR in lost
profit across all categories (12.2% of total realized profit), against
~39M SAR in discounts given — roughly half of every discounted SAR
bought back in extra sales, half was pure margin given away.

**Promo ranking** (`src/analysis/promo_ranking.py`) — merges promo lift and
margin erosion per SKU, ranked by net incremental profit, to surface the
best and worst individual performers.

**Finding: 0 of 500 SKUs (0.0%) ran a net-profitable promotion.** Even the
"best" (least-bad) SKUs lost roughly 2,000–5,000 SAR in incremental profit
vs. their non-promo baseline; the worst individual SKU lost ~259,000 SAR.
Combined with the revenue-lift finding above, most promotions in this
dataset aren't just costing margin — they often aren't even driving more
revenue for that specific product.

## Status

- [x] Data loader (`src/data/loader.py`)
- [x] Data cleaning (`src/data/cleaning.py`)
- [x] Feature engineering (`src/features/build_features.py`)
- [x] Parallel utility (`src/utils/parallel.py`)
- [x] Promo lift analysis (`src/analysis/promo_lift.py`) — SKU-level trustworthy, category-level flagged as unreliable
- [x] Margin erosion analysis (`src/analysis/margin_erosion.py`)
- [x] Promo ranking (`src/analysis/promo_ranking.py`)
- [ ] Price elasticity + returns
- [ ] Tests
- [ ] Pipeline orchestration + charts