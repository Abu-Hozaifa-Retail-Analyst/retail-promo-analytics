"""Promo lift analysis: sales/units uplift during promo vs non-promo periods."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.utils.parallel import run_grouped_parallel

MIN_DAYS_PER_REGIME = 3


def _daily_aggregate(sales_df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    return (
        sales_df.groupby(group_cols + ["transaction_date", "is_promo"])
        .agg(
            units=("quantity", "sum"),
            revenue=("net_sales", "sum"),
            profit=("profit_amount", "sum"),
        )
        .reset_index()
    )


def _lift_for_group(daily: pd.DataFrame) -> dict | None:
    promo = daily[daily["is_promo"]]
    nonpromo = daily[~daily["is_promo"]]

    if len(promo) < MIN_DAYS_PER_REGIME or len(nonpromo) < MIN_DAYS_PER_REGIME:
        return None

    avg_units_promo = promo["units"].mean()
    avg_units_nonpromo = nonpromo["units"].mean()
    avg_revenue_promo = promo["revenue"].mean()
    avg_revenue_nonpromo = nonpromo["revenue"].mean()

    unit_lift_pct = (
        (avg_units_promo - avg_units_nonpromo) / avg_units_nonpromo * 100
        if avg_units_nonpromo > 0
        else np.nan
    )
    revenue_lift_pct = (
        (avg_revenue_promo - avg_revenue_nonpromo) / avg_revenue_nonpromo * 100
        if avg_revenue_nonpromo > 0
        else np.nan
    )

    return {
        "n_promo_days": len(promo),
        "n_nonpromo_days": len(nonpromo),
        "avg_units_per_day_promo": round(avg_units_promo, 2),
        "avg_units_per_day_nonpromo": round(avg_units_nonpromo, 2),
        "unit_lift_pct": round(unit_lift_pct, 1) if pd.notna(unit_lift_pct) else np.nan,
        "avg_revenue_per_day_promo": round(avg_revenue_promo, 2),
        "avg_revenue_per_day_nonpromo": round(avg_revenue_nonpromo, 2),
        "revenue_lift_pct": round(revenue_lift_pct, 1)
        if pd.notna(revenue_lift_pct)
        else np.nan,
    }


def compute_promo_lift(
    sales_analysis_df: pd.DataFrame,
    group_cols: list[str] | None = None,
    *,
    n_jobs: int = -1,
) -> pd.DataFrame:
    """Compute promo vs non-promo per-day lift in units and revenue, per group."""
    group_cols = group_cols or ["product_id"]
    daily = _daily_aggregate(sales_analysis_df, group_cols)
    result = run_grouped_parallel(daily, group_cols, _lift_for_group, n_jobs=n_jobs)
    if not result.empty:
        result = result.sort_values("revenue_lift_pct", ascending=False).reset_index(
            drop=True
        )
    return result
