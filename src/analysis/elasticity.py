"""Price elasticity of demand, estimated per SKU via log-log regression."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from src.utils.parallel import run_grouped_parallel

MIN_DAYS_WITH_SALES = 15
MIN_DISTINCT_PRICE_POINTS = 4


def _daily_price_qty(sales_df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    """Collapse transactions to group x date: total units, qty-weighted avg price."""
    df = sales_df.assign(_price_x_qty=sales_df["unit_price"] * sales_df["quantity"])
    daily = (
        df.groupby(group_cols + ["transaction_date"])
        .agg(units=("quantity", "sum"), _price_x_qty_sum=("_price_x_qty", "sum"))
        .reset_index()
    )
    daily["avg_price"] = np.where(
        daily["units"] != 0, daily["_price_x_qty_sum"] / daily["units"], np.nan
    )
    return daily.drop(columns=["_price_x_qty_sum"])


def _elasticity_for_group(daily: pd.DataFrame) -> dict | None:
    daily = daily[(daily["units"] > 0) & (daily["avg_price"] > 0)]
    if len(daily) < MIN_DAYS_WITH_SALES:
        return None
    if daily["avg_price"].nunique() < MIN_DISTINCT_PRICE_POINTS:
        return None

    log_price = np.log(daily["avg_price"])
    log_units = np.log(daily["units"])
    reg = stats.linregress(log_price, log_units)

    return {
        "n_days": len(daily),
        "n_distinct_prices": int(daily["avg_price"].nunique()),
        "elasticity": round(reg.slope, 3),
        "r_squared": round(reg.rvalue**2, 3),
        "p_value": round(reg.pvalue, 4),
        "is_significant": bool(reg.pvalue < 0.05),
        "interpretation": "elastic (price-sensitive)"
        if abs(reg.slope) > 1
        else "inelastic (price-insensitive)",
        "avg_price": round(daily["avg_price"].mean(), 2),
        "avg_daily_units": round(daily["units"].mean(), 2),
    }


def compute_price_elasticity(
    sales_analysis_df: pd.DataFrame,
    group_cols: list[str] | None = None,
    *,
    n_jobs: int = -1,
) -> pd.DataFrame:
    """Estimate price elasticity of demand per group via log-log OLS."""
    group_cols = group_cols or ["product_id"]
    daily = _daily_price_qty(sales_analysis_df, group_cols)
    result = run_grouped_parallel(
        daily,
        group_cols,
        _elasticity_for_group,
        n_jobs=n_jobs,
        min_group_size=MIN_DAYS_WITH_SALES,
    )
    if not result.empty:
        result = result.sort_values("elasticity").reset_index(drop=True)
    return result
