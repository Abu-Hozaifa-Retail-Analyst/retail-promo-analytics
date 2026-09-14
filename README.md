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
during promo vs. non-promo periods, per SKU or category. Uses per-day averages
(not raw totals) to avoid bias from unequal promo/non-promo day counts, and
requires at least 3 days in each regime before trusting the comparison.

Current result (category level): every category shows positive revenue lift
during promotions, from +6.4% (Home Appliances) to +14.2% (Home & Living).
This confirms promotions drive volume — whether that volume is worth its
cost in margin is answered by the margin erosion analysis (next).

## Status

- [x] Data loader (`src/data/loader.py`)
- [x] Data cleaning (`src/data/cleaning.py`)
- [x] Feature engineering (`src/features/build_features.py`)
- [x] Parallel utility (`src/utils/parallel.py`)
- [x] Promo lift analysis (`src/analysis/promo_lift.py`)
- [ ] Margin erosion + promo ranking
- [ ] Price elasticity + returns
- [ ] Tests
- [ ] Pipeline orchestration + charts