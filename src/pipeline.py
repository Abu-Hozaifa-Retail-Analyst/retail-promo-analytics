"""End-to-end pipeline: load -> clean -> analyze -> save tables -> draw charts.

Run as a script:  python -m src.pipeline
Or import `run_full_pipeline()` from a notebook.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from src.analysis.breakeven import breakeven_table, discount_cost_summary
from src.analysis.diagnostics import run_promo_diagnostics
from src.analysis.pooled_elasticity import (
    estimate_pooled_elasticity,
    pooled_elasticity_by_group,
)
from src.analysis.returns import compute_return_rate
from src.analysis.scenarios import DEFAULT_CAPS, breakeven_elasticity, scenario_grid
from src.data.cleaning import clean_fact_sales, qa_summary_to_markdown
from src.data.loader import DEFAULT_DATA_DIR, load_all
from src.data.schema import SchemaError
from src.features.build_features import build_sales_analysis_table
from src.visualization import generate_all_charts

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "reports"
DEFAULT_FIGURES_DIR = PROJECT_ROOT / "outputs" / "figures"

# Elasticities drawn on the scenario chart: 0 (no reaction) down to -10 (extremely price-sensitive).
_CURVE_ELASTICITIES = tuple(np.round(np.arange(0.0, -10.01, -0.25), 2))

_ELASTICITY_SPECS = {
    "SKU effects": ("product_id",),
    "SKU + week effects": ("product_id", "year_week"),
    "SKU + store effects": ("product_id", "store_id"),
}


def run_full_pipeline(
    data_dir: Path = DEFAULT_DATA_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    figures_dir: Path = DEFAULT_FIGURES_DIR,
    make_charts: bool = True,
    n_jobs: int = -1,
) -> dict:
    """Run the full analysis, write result tables (and charts) to disk, and return everything.

    Args:
        data_dir: Directory with the five raw CSVs.
        output_dir: Where result tables, the QA report and JSON summaries are written.
        figures_dir: Where charts are written.
        make_charts: Skip chart drawing when False (useful in tests).
        n_jobs: Parallel workers for per-category estimates (-1 = all cores).

    Returns:
        Dict of result tables and summaries, also reusable from a notebook.
    """
    output_dir, figures_dir = Path(output_dir), Path(figures_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Loading raw tables from %s", data_dir)
    tables = load_all(data_dir)

    logger.info("Cleaning fact_sales (dedup, validation, canonical recompute)")
    sales_clean, qa = clean_fact_sales(
        tables["sales"],
        tables["customer"],
        tables["product"],
        tables["store"],
        tables["date"],
    )
    (output_dir / "qa_report.md").write_text(qa_summary_to_markdown(qa))
    (output_dir / "qa_report.json").write_text(json.dumps(qa.as_dict(), indent=2))
    logger.info(
        "QA: %s raw -> %s valid rows (%s invalid, %s duplicates removed, %s returns)",
        qa.total_rows_raw,
        qa.total_valid_rows,
        qa.total_invalid_rows,
        qa.duplicate_rows_removed,
        qa.return_rows,
    )

    logger.info("Building the analysis table")
    analysis = build_sales_analysis_table(sales_clean, tables["customer"], tables["store"], tables["date"])
    analysis["year_week"] = analysis["year"].astype(str) + "-" + analysis["week"].astype(str)

    logger.info("Running promo data diagnostics")
    diagnostics = run_promo_diagnostics(analysis)

    logger.info("Estimating pooled price elasticity (overall, with seasonality/store effects, by category)")
    pooled = pd.DataFrame(
        [
            {
                "specification": name,
                **estimate_pooled_elasticity(analysis, fixed_effects=fe),
            }
            for name, fe in _ELASTICITY_SPECS.items()
        ]
    )
    pooled_by_category = pooled_elasticity_by_group(analysis, "category", n_jobs=n_jobs)

    logger.info("Computing break-even volume lift and the discount cost summary")
    breakeven = breakeven_table(analysis)
    discount_cost = discount_cost_summary(analysis)

    logger.info("Simulating discount caps")
    grid = scenario_grid(analysis)
    curve = scenario_grid(analysis, DEFAULT_CAPS, _CURVE_ELASTICITIES)
    breakeven_elast = pd.DataFrame(
        [
            {
                "cap": cap,
                "breakeven_elasticity": round(breakeven_elasticity(analysis, cap), 2),
            }
            for cap in DEFAULT_CAPS
        ]
    )

    logger.info("Computing return rates by category")
    return_rate = compute_return_rate(sales_clean, ["category"])

    demand = diagnostics["demand_response"]
    summary = {
        "promo_share_pct": diagnostics["promo_share_pct"],
        "sparsity": diagnostics["sparsity"],
        "persistence": diagnostics["persistence"],
        "demand_response": {k: v for k, v in demand.items() if k != "by_depth"},
        "discount_cost": discount_cost,
    }
    (output_dir / "diagnostics_summary.json").write_text(json.dumps(summary, indent=2))

    tables_to_save = {
        "promo_assignment": diagnostics["assignment"],
        "demand_by_depth": demand["by_depth"].reset_index(),
        "pooled_elasticity": pooled,
        "pooled_elasticity_by_category": pooled_by_category,
        "breakeven": breakeven,
        "scenario_grid": grid,
        "scenario_curve": curve,
        "breakeven_elasticity": breakeven_elast,
        "return_rate_category": return_rate,
    }
    for name, df in tables_to_save.items():
        df.to_csv(output_dir / f"{name}.csv", index=False)

    results = {
        "analysis_df": analysis,
        "diagnostics": diagnostics,
        "discount_cost": discount_cost,
        **tables_to_save,
    }

    if make_charts:
        logger.info("Drawing charts into %s", figures_dir)
        results["chart_paths"] = generate_all_charts(results, figures_dir)

    logger.info("Pipeline complete. Tables written to %s", output_dir)
    return results


if __name__ == "__main__":
    try:
        run_full_pipeline()
    except SchemaError as error:
        raise SystemExit(f"\n{error}") from None
