"""Return-rate and net-profit-impact reporting."""

from __future__ import annotations

import pandas as pd


def compute_return_rate(
    sales_clean: pd.DataFrame, group_cols: list[str] | None = None
) -> pd.DataFrame:
    """Compute return rate and net profit impact per group."""
    group_cols = group_cols or ["category"]
    valid = sales_clean[sales_clean["is_valid"]]

    sold = valid[~valid["is_return"]]
    returned = valid[valid["is_return"]]

    sold_agg = sold.groupby(group_cols).agg(
        gross_units_sold=("quantity", "sum"), gross_profit=("profit_amount", "sum")
    )
    returned_agg = returned.groupby(group_cols).agg(
        returned_units=("quantity", lambda s: s.abs().sum()),
        returned_profit=("profit_amount", lambda s: s.abs().sum()),
    )

    out = sold_agg.join(returned_agg, how="left").fillna(0.0)
    out["return_rate_pct"] = (
        (out["returned_units"] / out["gross_units_sold"] * 100)
        .where(out["gross_units_sold"] > 0)
        .round(2)
    )
    out["net_profit"] = (out["gross_profit"] - out["returned_profit"]).round(2)
    out = out.reset_index().sort_values("return_rate_pct", ascending=False)
    return out.reset_index(drop=True)
