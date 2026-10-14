# Retail Promotion & Profitability Analytics

[![CI](https://github.com/Abu-Hozaifa-Retail-Analyst/retail-promo-analytics/actions/workflows/ci.yml/badge.svg)](https://github.com/Abu-Hozaifa-Retail-Analyst/retail-promo-analytics/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

> **Key finding.** In this dataset, discounts do not measurably change how much customers buy:
> pooled price elasticity is **−0.003 (95% CI −0.049 to +0.042)**. Every discount is therefore
> margin given away unless it brings in extra transactions, which this data cannot observe.
> Discounts total **39.0M SAR, equal to 23.5% of realized profit**.
>
> ⚠️ `STAKEHOLDER_SUMMARY.md` predates a methodology review and is being rewritten. Its headline
> figures (20.2M SAR lost, "0 of 500 SKUs profitable") are **superseded**; see
> [Legacy analyses and known limitations](#legacy-analyses-and-known-limitations).

## Questions this project answers

1. **Can this dataset support a promotion-effect analysis at all?** (data diagnostics)
2. **Do discounts change what customers buy?** (demand response and price elasticity)
3. **What do discounts cost?** (margin given away)
4. **Which discount depths could ever pay for themselves?** (break-even analysis, in progress)

## Findings so far

| Question | Result | Code |
|---|---|---|
| Is there a promo calendar? | **No.** 54.8% of transactions carry a discount, flat across category, region, store type, weekday and month (spread ≤ 1.5 pts). P(promo \| previous transaction was promo) = 0.545 vs 0.552 otherwise, so discounting behaves like an independent per-transaction coin flip, not planned events. | `diagnostics.py` |
| Is the SKU × day panel dense? | **No.** 72.2% of SKU-days have zero sales; days with sales average 1.17 transactions. | `diagnostics.py` |
| Does quantity per transaction rise with a discount? | **No.** 3.003 units on promo vs 3.008 off promo: lift −0.15%, 95% CI [−0.69%, +0.39%]. | `diagnostics.py` |
| What is the price elasticity? | **−0.003, 95% CI [−0.049, +0.042]**, from 118,664 transactions and 500 SKUs. Unchanged with week effects (−0.004) or store effects (−0.003). All 7 categories have intervals that include 0 and exclude −1. | `pooled_elasticity.py` |
| What do discounts cost? | **39.0M SAR given**, 23.5% of 166.0M SAR profit. | `margin_erosion.py` output (`total_discount_given`) |
| Do returns matter? | No. Return rates are 0.19–0.32% by category. | `returns.py` |

### What this data cannot tell us

- **Traffic effects.** Quantity per transaction does not respond to discounts, but a discount could still
  bring in *more transactions*. Transactions only exist when a sale happened, and discounts are assigned
  per transaction rather than per period, so the extra transactions a discount might create cannot be
  observed here.
- **Anything about planned promotions.** There is no promo calendar in the data (see the first row above).

**What would fix it:** a promotion calendar from the planning system (SKU, store, start and end date,
mechanic), joined to the sales data, so promo periods can be compared with comparable non-promo periods.

## How the analysis works

```
raw CSVs ──► loader ──► cleaning (flag, don't drop) ──► analysis table ──► diagnostics
                                                                      └──► pooled elasticity
```

1. **Load** the five star-schema tables (`src/data/loader.py`).
2. **Clean** `fact_sales`: deduplicate, flag invalid rows, separate returns, recompute financial fields
   (`src/data/cleaning.py`).
3. **Build the analysis table**: join dimensions and derive `is_promo` and `discount_pct`
   (`src/features/build_features.py`).
4. **Diagnose** whether the data can support a promotion-effect analysis
   (`src/analysis/diagnostics.py`).
5. **Estimate** one price elasticity with SKU fixed effects and SKU-clustered standard errors
   (`src/analysis/pooled_elasticity.py`).

## Project structure

```
retail-promo-analytics/
├── .github/workflows/ci.yml        # run tests on every push to main and on pull requests
├── src/
│   ├── data/
│   │   ├── loader.py               # read raw CSVs from data/raw/
│   │   └── cleaning.py             # dedup, validity flags, canonical recompute, QA summary
│   ├── features/
│   │   └── build_features.py       # joins, is_promo, discount_pct, depth buckets
│   ├── analysis/
│   │   ├── diagnostics.py          # can the data support a promo analysis?
│   │   ├── pooled_elasticity.py    # fixed-effects elasticity, clustered standard errors
│   │   ├── returns.py              # return rate and net profit impact
│   │   ├── promo_lift.py           # legacy (see known limitations)
│   │   ├── margin_erosion.py       # legacy
│   │   ├── promo_ranking.py        # legacy
│   │   └── elasticity.py           # legacy per-SKU regressions
│   ├── utils/parallel.py           # joblib wrapper for independent per-group work
│   ├── visualization.py            # matplotlib / seaborn charts
│   └── pipeline.py                 # load -> clean -> legacy analyses -> save
├── tests/                          # 36 pytest tests
├── data/raw/                       # your 5 source CSVs go here (gitignored)
├── outputs/                        # generated tables and charts (gitignored)
├── pytest.ini
├── requirements.txt
├── STAKEHOLDER_SUMMARY.md          # being rewritten
└── LICENSE
```

## Setup

Python 3.11 or newer (CI runs 3.11; developed on 3.13).

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

## Data expectations

Place these five CSVs in `data/raw/` (star schema, not included in the repo):

| File | Grain | Key columns |
|---|---|---|
| `dim_customer.csv` | 1 row / customer | `customer_id`, `customer_segment`, `gender`, `age`, `city` |
| `dim_date.csv` | 1 row / calendar date | `date_key`, `date`, `year`, `quarter`, `month`, `week` |
| `dim_product.csv` | 1 row / SKU | `product_id`, `category`, `unit_cost`, `selling_price` |
| `dim_store.csv` | 1 row / store | `store_id`, `region`, `store_type` |
| `fact_sales.csv` | 1 row / transaction line | `transaction_id`, `transaction_date`, `customer_id`, `product_id`, `store_id`, `quantity`, `unit_price`, `discount_amount`, `unit_cost` |

There is no explicit promo flag. A transaction counts as **promoted** if `discount_amount > 0`
(defined in `src/features/build_features.py`). The diagnostics above show that, in this dataset,
that is a per-transaction attribute rather than a promotion event.

## Data quality handling

Real POS data has issues. They are handled explicitly rather than silently:

| Issue | Handling |
|---|---|
| Duplicate `transaction_id` | Deduplicated (keep first) |
| Bad `product_id` / `store_id` foreign key, zero quantity, non-positive price, date outside calendar | **Kept**, flagged `is_valid=False` with a reason in `invalid_reasons`; excluded only from aggregates |
| Negative quantity | Treated as a **return** (`is_return=True`), not a data error: kept valid, analyzed separately |
| `customer_id` present but not in `dim_customer` | **Kept**, flagged `has_valid_customer=False` (separate from `is_valid`, since a bad customer link does not affect revenue or margin math, only customer-level cuts) |
| Provided `gross_sales`, `net_sales`, `profit_amount`, `gross_margin_pct` | **Recomputed** from base fields; disagreements flagged `qa_mismatch=True` |

Results on this dataset:

| Metric | Value |
|---|---|
| Raw rows | 120,680 |
| Duplicate rows removed | 680 |
| Invalid rows (excluded from aggregates) | 847 |
| Valid rows | 119,153 |
| Return rows (kept, analyzed separately) | 296 |
| Valid non-return transactions in the analysis table | 118,858 |
| Financial field mismatches (source vs recomputed) | 495 to 1,087 depending on field |

The pipeline writes the full report to `outputs/reports/qa_report.md`.

## Running the analysis

Run the pipeline (loads, cleans, runs the legacy analyses, writes tables and a QA report to
`outputs/reports/`):

```powershell
python -m src.pipeline
```

Always use `python -m src.pipeline`, not `python src/pipeline.py`. The `-m` flag puts the project root
on the import path so `from src...` imports resolve.

Run the diagnostics and the pooled elasticity (not yet wired into the pipeline):

```python
from src.data.loader import load_all
from src.data.cleaning import clean_fact_sales
from src.features.build_features import build_sales_analysis_table
from src.analysis.diagnostics import run_promo_diagnostics
from src.analysis.pooled_elasticity import estimate_pooled_elasticity, pooled_elasticity_by_group

tables = load_all()
cleaned, qa = clean_fact_sales(
    tables["sales"], tables["customer"], tables["product"], tables["store"], tables["date"]
)
analysis = build_sales_analysis_table(cleaned, tables["customer"], tables["store"], tables["date"])
analysis["year_week"] = analysis["year"].astype(str) + "-" + analysis["week"].astype(str)

diagnostics = run_promo_diagnostics(analysis)
overall = estimate_pooled_elasticity(analysis)
with_seasonality = estimate_pooled_elasticity(analysis, fixed_effects=("product_id", "year_week"))
by_category = pooled_elasticity_by_group(analysis, "category")
```

### Charts

`src/visualization.py` generates PNGs into `outputs/figures/`. The current chart set is built from the
legacy analyses, so treat `promo_profitability_scatter.png` as superseded until the charts are rebuilt
(see the roadmap).

## Legacy analyses and known limitations

`promo_lift.py`, `margin_erosion.py`, `promo_ranking.py` and `elasticity.py` compare "promo days" with
"non-promo days" per SKU or category. A methodology review found problems that make their headline
numbers unreliable. They remain in the repo, and the pipeline still runs them, until the replacements
land.

| Limitation | Why it matters |
|---|---|
| The daily grouping only creates rows for days that had a sale | 72% of SKU-days are ignored, and "units per day" is effectively quantity per transaction |
| Promo status is set per transaction | One calendar day can fall into both regimes, and there are no real promo periods to compare |
| Category-level lift compares buckets of unequal size (about 55% vs 45% of transactions) | It showed positive lift for every category and contradicted the SKU level; treat it as an artifact |
| SKU-level "negative revenue lift" mostly reflects the discount itself | Revenue per transaction is 10.3% lower on promos against an average depth of 9.5%, because quantity does not respond |
| Incremental-profit totals depend on the grouping | The same code gives 20.2M SAR at category level and 37.8M SAR at SKU level, so neither is a reliable headline |
| Per-SKU elasticity regressions use about 240 transactions each | Estimates are noise around zero (only 2% significant); replaced by the pooled estimate |

The earlier headline "0 of 500 SKUs ran a profitable promotion" follows mechanically from the fifth row:
with no quantity response, profit per transaction must fall by the discount. It describes the data, not
a finding about promotion strategy.

## Testing

```powershell
pytest -v
```

36 tests:

| File | Tests | Covers |
|---|---|---|
| `test_cleaning.py` | 12 | One test per data-quality rule, QA summary |
| `test_build_features.py` | 4 | Promo derivation, joins, default exclusions |
| `test_parallel.py` | 4 | Grouping, key handling, filtering |
| `test_promo_analysis.py` | 3 | Legacy lift, erosion and ranking math against hand-checked fixtures |
| `test_elasticity_and_returns.py` | 4 | Legacy elasticity (known slope recovered), guard conditions, return rate |
| `test_diagnostics.py` | 5 | Sparsity, assignment profile, persistence, demand response |
| `test_pooled_elasticity.py` | 4 | Known elasticity recovered, zero response, and week effects removing seasonal confounding |

The pooled elasticity tests use data generated from a **known** elasticity. One test builds busy weeks
that have both more discounting and more demand: the naive estimate is −3.6 against a true −1.0, and
adding week effects recovers −0.98.

## Continuous integration

GitHub Actions (`.github/workflows/ci.yml`) runs the full test suite on every push to `main` and on every
pull request targeting `main`, on Python 3.11.

## Lessons learned

- pandas and NumPy return their own boolean type (`np.bool_`), so `is True` fails on correct values. Use
  `assert x` or `assert not x`.
- `np.isclose` defaults are far tighter than typical rounding; pass an explicit `atol`.
- When a shared fixture in `conftest.py` changes, every test that uses it needs re-checking.
- Only third-party packages belong in `requirements.txt`. `json`, `logging` and `pathlib` ship with Python.
- Aggregation can hide the truth: always check how much of the panel is empty and how many events each
  group contains before trusting a daily average.
- Seasonality inflates promo effects: when busy weeks have both more discounts and more demand, a naive
  elasticity looks far too large. Fixed effects fix it.
- Cluster-robust standard errors are only well calibrated with enough clusters (about 100 here vs 20).

## Roadmap

- [x] Loader, cleaning, feature engineering, parallel utility
- [x] Legacy lift, erosion, ranking, elasticity and returns analyses
- [x] Tests and CI
- [x] Data diagnostics
- [x] Pooled fixed-effects elasticity
- [ ] Break-even and below-cost guardrail module (the volume lift each discount depth needs to hold profit
      flat; an initial audit found 2,240 promo transactions priced below cost)
- [ ] Complete SKU × week panel with zero-sales periods filled in, for traffic-based analysis
- [ ] Discount-cap scenario simulation with sensitivity to the assumed elasticity
- [ ] Wire diagnostics and pooled elasticity into the pipeline and rebuild the charts
- [ ] Input schema validation
- [ ] Engineering polish: `pyproject.toml`, ruff, mypy, coverage, Python version matrix
- [ ] Rewrite `STAKEHOLDER_SUMMARY.md` around the corrected findings
- [ ] Notebook walkthrough
- [ ] Repository description and topics, `v1.0` release

## License

MIT. See [LICENSE](LICENSE).
