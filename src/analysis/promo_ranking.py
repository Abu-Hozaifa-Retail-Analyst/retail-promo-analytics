"""Best/worst performing promotions, ranked by net incremental profit."""

from __future__ import annotations

import pandas as pd

from src.analysis.margin_erosion import compute_margin_erosion
from src.analysis.promo_lift import compute_promo_lift


def rank_promotions(
    sales_analysis_df: pd.DataFrame,
    group_cols: list[str] | None = None,
    *,
    n_jobs: int = -1,
    top_n: int = 10,
) -> dict[str, pd.DataFrame]:
    """Rank groups by net incremental promo profit; surface best/worst."""
    group_cols = group_cols or ["product_id"]

    lift = compute_promo_lift(sales_analysis_df, group_cols, n_jobs=n_jobs)
    erosion = compute_margin_erosion(sales_analysis_df, group_cols, n_jobs=n_jobs)

    if lift.empty or erosion.empty:
        empty = pd.DataFrame()
        return {"full": empty, "best": empty, "worst": empty}

    full = lift.merge(
        erosion.drop(columns=["n_promo_days", "n_nonpromo_days"]),
        on=group_cols,
        how="inner",
    )
    full = full.sort_values(
        "incremental_profit_vs_baseline", ascending=False
    ).reset_index(drop=True)

    best = full.head(top_n).reset_index(drop=True)
    worst = (
        full.tail(top_n)
        .sort_values("incremental_profit_vs_baseline")
        .reset_index(drop=True)
    )

    return {"full": full, "best": best, "worst": worst}
