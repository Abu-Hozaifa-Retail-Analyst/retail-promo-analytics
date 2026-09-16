"""End-to-end pipeline: load -> clean -> feature-build -> analyze -> save."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd

from src.analysis.elasticity import compute_price_elasticity
from src.analysis.margin_erosion import compute_margin_erosion
from src.analysis.promo_lift import compute_promo_lift
from src.analysis.promo_ranking import rank_promotions
from src.analysis.returns import compute_return_rate
from src.data.cleaning import clean_fact_sales, qa_summary_to_markdown
from src.data.loader import DEFAULT_DATA_DIR, load_all
from src.features.build_features import build_sales_analysis_table

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "reports"


def run_full_pipeline(
    data_dir: Path = DEFAULT_DATA_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    n_jobs: int = -1,
) -> dict[str, pd.DataFrame]:
    """Run the full load -> clean -> analyze pipeline and persist results."""
    output_dir = Path(output_dir)
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

    logger.info("Building sales analysis table")
    analysis_df = build_sales_analysis_table(
        sales_clean, tables["customer"], tables["store"], tables["date"]
    )

    logger.info("Computing promo lift (SKU and category level)")
    promo_lift_sku = compute_promo_lift(analysis_df, ["product_id"], n_jobs=n_jobs)
    promo_lift_category = compute_promo_lift(analysis_df, ["category"], n_jobs=n_jobs)

    logger.info("Computing margin erosion (SKU and category level)")
    margin_erosion_sku = compute_margin_erosion(
        analysis_df, ["product_id"], n_jobs=n_jobs
    )
    margin_erosion_category = compute_margin_erosion(
        analysis_df, ["category"], n_jobs=n_jobs
    )

    logger.info("Ranking promotions (SKU level)")
    ranking = rank_promotions(analysis_df, ["product_id"], n_jobs=n_jobs, top_n=15)

    logger.info("Estimating price elasticity (SKU level)")
    elasticity_sku = compute_price_elasticity(
        analysis_df, ["product_id"], n_jobs=n_jobs
    )

    logger.info("Computing return rates by category")
    return_rate_category = compute_return_rate(sales_clean, ["category"])

    results = {
        "analysis_df": analysis_df,
        "promo_lift_sku": promo_lift_sku,
        "promo_lift_category": promo_lift_category,
        "margin_erosion_sku": margin_erosion_sku,
        "margin_erosion_category": margin_erosion_category,
        "ranking_full": ranking["full"],
        "ranking_best": ranking["best"],
        "ranking_worst": ranking["worst"],
        "elasticity_sku": elasticity_sku,
        "return_rate_category": return_rate_category,
    }

    for name, df in results.items():
        if name == "analysis_df":
            continue  # row-level data, not a result table -- don't persist it
        df.to_csv(output_dir / f"{name}.csv", index=False)

    logger.info("Pipeline complete. Result tables written to %s", output_dir)
    return results


if __name__ == "__main__":
    run_full_pipeline()
