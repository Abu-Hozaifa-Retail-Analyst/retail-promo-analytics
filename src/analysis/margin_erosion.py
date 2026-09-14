"""Margin erosion analysis: how much profit promotions cost vs. drive."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.utils.parallel import run_grouped_parallel

MIN_DAYS_PER_REGIME = 3


def _daily_aggregate(sales_df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    agg = (
        sales_df.groupby(group_cols + ["transaction_date", "is_promo"])
        .agg(
            profit=("profit_amount", "sum"),
            revenue=("net_sales", "sum"),
            discount=("discount_amount", "sum"),
        )
        .reset_index()
    )
    agg["margin_pct"] = np.where(
        agg["revenue"] != 0, agg["profit"] / agg["revenue"] * 100, np.nan
    )
    return agg


def _erosion_for_group(daily: pd.DataFrame) -> dict | None:
    promo = daily[daily["is_promo"]]
    nonpromo = daily[~daily["is_promo"]]

    if len(promo) < MIN_DAYS_PER_REGIME or len(nonpromo) < MIN_DAYS_PER_REGIME:
        return None

    margin_promo = promo["margin_pct"].mean()
    margin_nonpromo = nonpromo["margin_pct"].mean()
    erosion_pts = margin_nonpromo - margin_promo

    avg_profit_promo = promo["profit"].mean()
    avg_profit_nonpromo = nonpromo["profit"].mean()
    incremental_profit_total = (avg_profit_promo - avg_profit_nonpromo) * len(promo)
    total_discount_given = promo["discount"].sum()

    return {
        "n_promo_days": len(promo),
        "n_nonpromo_days": len(nonpromo),
        "avg_margin_pct_promo": round(margin_promo, 2)
        if pd.notna(margin_promo)
        else np.nan,
        "avg_margin_pct_nonpromo": round(margin_nonpromo, 2)
        if pd.notna(margin_nonpromo)
        else np.nan,
        "margin_erosion_pts": round(erosion_pts, 2)
        if pd.notna(erosion_pts)
        else np.nan,
        "total_discount_given": round(total_discount_given, 2),
        "incremental_profit_vs_baseline": round(incremental_profit_total, 2),
        "promo_profitable": bool(incremental_profit_total > 0),
    }


def compute_margin_erosion(
    sales_analysis_df: pd.DataFrame,
    group_cols: list[str] | None = None,
    *,
    n_jobs: int = -1,
) -> pd.DataFrame:
    """Compute margin-rate erosion and net incremental profit per group."""
    group_cols = group_cols or ["product_id"]
    daily = _daily_aggregate(sales_analysis_df, group_cols)
    result = run_grouped_parallel(daily, group_cols, _erosion_for_group, n_jobs=n_jobs)
    if not result.empty:
        result = result.sort_values(
            "incremental_profit_vs_baseline", ascending=False
        ).reset_index(drop=True)
    return result
