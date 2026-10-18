"""End-to-end test of the pipeline on a small synthetic star schema.

The real data is gitignored, so without this test CI would never run the pipeline
and a broken import or a renamed column could reach `main` unnoticed.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault(
    "MPLBACKEND", "Agg"
)  # draw charts without a display; read when matplotlib is first imported

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.pipeline import run_full_pipeline  # noqa: E402

EXPECTED_TABLES = {
    "qa_report.md",
    "qa_report.json",
    "diagnostics_summary.json",
    "promo_assignment.csv",
    "demand_by_depth.csv",
    "pooled_elasticity.csv",
    "pooled_elasticity_by_category.csv",
    "breakeven.csv",
    "scenario_grid.csv",
    "scenario_curve.csv",
    "breakeven_elasticity.csv",
    "return_rate_category.csv",
}
EXPECTED_CHARTS = {
    "breakeven_gap.png",
    "scenario_profit_curves.png",
    "elasticity_estimates.png",
    "return_rate_by_category.png",
}


def _write_synthetic_star_schema(data_dir: Path, seed: int = 0) -> None:
    """Write five small CSVs in the real schema, with three planted data problems."""
    rng = np.random.default_rng(seed)
    n_sku, n_cust, n_txn = 40, 60, 6000
    dates = pd.date_range("2024-01-01", "2024-06-30", freq="D")
    date_str = dates.strftime("%Y-%m-%d")

    pd.DataFrame(
        {
            "date_key": dates.strftime("%Y%m%d").astype(int),
            "date": date_str,
            "year": dates.year,
            "quarter": dates.quarter,
            "month": dates.month,
            "month_name": dates.strftime("%B"),
            "week": dates.isocalendar().week.to_numpy(),
            "day": dates.day,
            "day_of_week": dates.dayofweek,
            "day_name": dates.strftime("%A"),
        }
    ).to_csv(data_dir / "dim_date.csv", index=False)

    skus = [f"P{i:03d}" for i in range(n_sku)]
    unit_cost = rng.uniform(50, 150, n_sku).round(2)
    product = pd.DataFrame(
        {
            "product_id": skus,
            "product_name": [f"Item {i}" for i in range(n_sku)],
            "category": ["Alpha" if i % 2 == 0 else "Beta" for i in range(n_sku)],
            "subcategory": "Sub",
            "brand": "Brand",
            "unit_cost": unit_cost,
            "selling_price": (unit_cost * 1.4).round(2),
        }
    )
    product.to_csv(data_dir / "dim_product.csv", index=False)

    pd.DataFrame(
        {
            "store_id": ["S01", "S02", "S03"],
            "store_name": ["One", "Two", "Three"],
            "city": ["Riyadh", "Jeddah", "Dammam"],
            "region": ["Central", "Western", "Eastern"],
            "store_type": ["Mall", "Hypermarket", "Mall"],
        }
    ).to_csv(data_dir / "dim_store.csv", index=False)

    pd.DataFrame(
        {
            "customer_id": [f"C{i:03d}" for i in range(n_cust)],
            "customer_name": [f"Customer {i}" for i in range(n_cust)],
            "gender": "Female",
            "age": 30,
            "city": "Riyadh",
            "customer_segment": "Standard",
        }
    ).to_csv(data_dir / "dim_customer.csv", index=False)

    idx = rng.integers(0, n_sku, n_txn)
    qty = rng.integers(1, 6, n_txn)
    price = product["selling_price"].to_numpy()[idx]
    cost = product["unit_cost"].to_numpy()[idx]
    depth = rng.choice(
        [0.0, 0.0, 0.05, 0.10, 0.15, 0.20], n_txn
    )  # discounts independent of quantity
    gross = qty * price
    discount = (gross * depth).round(2)
    net = gross - discount
    profit = net - qty * cost
    fact = pd.DataFrame(
        {
            "transaction_id": [f"T{i:06d}" for i in range(n_txn)],
            "transaction_date": rng.choice(date_str, n_txn),
            "customer_id": [f"C{i:03d}" for i in rng.integers(0, n_cust, n_txn)],
            "product_id": np.array(skus)[idx],
            "store_id": [f"S{i:02d}" for i in rng.integers(1, 4, n_txn)],
            "quantity": qty,
            "unit_price": price,
            "discount_amount": discount,
            "gross_sales": gross,
            "net_sales": net,
            "unit_cost": cost,
            "cost_amount": qty * cost,
            "profit_amount": profit,
            "gross_margin_pct": profit / net * 100,
            "payment_method": "Card",
            "sales_channel": "Store",
            "category": product["category"].to_numpy()[idx],
        }
    )
    planted = [
        fact.iloc[0].to_dict(),  # an exact duplicate of the first row
        {
            **fact.iloc[1].to_dict(),
            "transaction_id": "T900001",
            "discount_amount": fact.iloc[1]["gross_sales"] * 1.5,
        },
        {
            **fact.iloc[2].to_dict(),
            "transaction_id": "T900002",
            "quantity": -1,
        },  # a return
    ]
    pd.concat([fact, pd.DataFrame(planted)], ignore_index=True).to_csv(
        data_dir / "fact_sales.csv", index=False
    )


def _run(tmp_path: Path, make_charts: bool) -> tuple[dict, Path, Path]:
    data_dir, out, fig = tmp_path / "raw", tmp_path / "reports", tmp_path / "figures"
    data_dir.mkdir()
    _write_synthetic_star_schema(data_dir)
    results = run_full_pipeline(
        data_dir=data_dir,
        output_dir=out,
        figures_dir=fig,
        make_charts=make_charts,
        n_jobs=1,
    )
    return results, out, fig


def test_pipeline_writes_every_table_and_chart(tmp_path):
    results, out, fig = _run(tmp_path, make_charts=True)
    assert EXPECTED_TABLES <= {p.name for p in out.iterdir()}
    assert {p.name for p in fig.glob("*.png")} == EXPECTED_CHARTS
    assert all(p.stat().st_size > 0 for p in fig.glob("*.png"))
    assert len(results["chart_paths"]) == 4


def test_pipeline_counts_planted_problems_and_satisfies_known_identities(tmp_path):
    results, out, _ = _run(tmp_path, make_charts=False)

    qa = json.loads((out / "qa_report.json").read_text())
    assert qa["total_rows_raw"] == 6003
    assert qa["duplicate_rows_removed"] == 1
    assert qa["invalid_discount_exceeds_gross"] == 1
    assert qa["return_rows"] == 1

    assert len(results["pooled_elasticity"]) == 3
    assert len(results["scenario_grid"]) == 24  # 4 caps x 6 elasticities
    assert (results["breakeven_elasticity"]["breakeven_elasticity"] < 0).all()

    # Removing every discount with no volume reaction gains exactly the discounts given.
    grid, cost = results["scenario_grid"], results["discount_cost"]
    gain = grid[(grid["cap"] == 0.0) & (grid["elasticity"] == 0.0)][
        "profit_change"
    ].iloc[0]
    assert abs(gain - cost["total_discount_given"]) <= 1
