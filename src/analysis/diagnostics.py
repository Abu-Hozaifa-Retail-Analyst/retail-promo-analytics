"""Diagnostics: can this dataset actually support a promotion-effect analysis?

These checks run BEFORE any lift / elasticity number is computed. Each one
answers a question that, if the answer is "no", changes how every later
result must be interpreted.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

_DEFAULT_DIMS = [
    "category",
    "region",
    "store_type",
    "day_name",
    "month",
    "customer_segment",
]


def panel_sparsity(df: pd.DataFrame, n_days: int | None = None) -> dict[str, float]:
    """How much of the full SKU x day grid actually has a sale?

    A lift calculation built on daily totals silently ignores every SKU-day
    with zero sales. If most days are empty, "units per day" really means
    "units per transaction", and traffic effects are invisible.

    Args:
        df: Analysis table with `product_id` and `transaction_date`.
        n_days: Number of calendar days in the panel. Defaults to the span
            between the first and last transaction date.
    """
    if n_days is None:
        n_days = (df["transaction_date"].max() - df["transaction_date"].min()).days + 1
    total_cells = df["product_id"].nunique() * n_days
    per_cell = df.groupby(["product_id", "transaction_date"]).size()
    pct_active = len(per_cell) / total_cells * 100
    return {
        "sku_days_total": int(total_cells),
        "sku_days_with_sales": int(len(per_cell)),
        "pct_sku_days_with_sales": round(pct_active, 1),
        "pct_sku_days_zero_sales": round(100 - pct_active, 1),
        "avg_txns_per_active_sku_day": round(float(per_cell.mean()), 2),
    }


def promo_assignment_profile(df: pd.DataFrame, dims: list[str] | None = None) -> pd.DataFrame:
    """Does the promo share vary across categories, stores, weekdays, months...?

    A real promotional calendar is targeted: some categories, stores and
    periods get far more discounting than others. A near-flat share
    everywhere suggests discounts are not planned events.
    """
    dims = [d for d in (dims or _DEFAULT_DIMS) if d in df.columns]
    rows = []
    for dim in dims:
        share = df.groupby(dim)["is_promo"].mean() * 100
        rows.append(
            {
                "dimension": dim,
                "min_promo_share_pct": round(share.min(), 1),
                "max_promo_share_pct": round(share.max(), 1),
                "spread_pts": round(share.max() - share.min(), 1),
            }
        )
    return pd.DataFrame(rows)


def promo_persistence(df: pd.DataFrame) -> dict[str, float]:
    """Does a SKU's promo status carry over from one transaction to the next?

    Promotion events last days or weeks, so P(promo | previous was promo)
    should be much higher than P(promo | previous was not). If the two are
    equal, discounting behaves like an independent coin flip per transaction.
    """
    cols = ["product_id", "transaction_date"]
    if "transaction_id" in df.columns:
        cols.append("transaction_id")
    d = df.sort_values(cols, kind="stable")
    prev = d.groupby("product_id")["is_promo"].shift()
    after_promo = d.loc[prev == True, "is_promo"].mean()  # noqa: E712
    after_non = d.loc[prev == False, "is_promo"].mean()  # noqa: E712
    return {
        "p_promo_after_promo": round(float(after_promo), 3),
        "p_promo_after_nonpromo": round(float(after_non), 3),
        "gap": round(float(after_promo - after_non), 3),
    }


def demand_response(df: pd.DataFrame) -> dict[str, Any]:
    """Does quantity per transaction rise when a discount is given?

    Returns the quantity lift (promo vs non-promo) with a 95% confidence
    interval, the discount/quantity correlation, and a breakdown by depth.
    """
    promo, non = df[df["is_promo"]], df[~df["is_promo"]]
    base = non["quantity"].mean()
    diff = promo["quantity"].mean() - base
    se = np.sqrt(promo["quantity"].var() / len(promo) + non["quantity"].var() / len(non))
    by_depth = (
        df.groupby("promo_depth_bucket", observed=True)
        .agg(
            txns=("quantity", "size"),
            avg_qty=("quantity", "mean"),
            avg_profit_per_txn=("profit_amount", "mean"),
            avg_margin_pct=("gross_margin_pct", "mean"),
        )
        .round(2)
    )
    return {
        "qty_lift_pct": round(float(diff / base * 100), 2),
        "qty_lift_ci_low_pct": round(float((diff - 1.96 * se) / base * 100), 2),
        "qty_lift_ci_high_pct": round(float((diff + 1.96 * se) / base * 100), 2),
        "corr_discount_qty": round(float(df["discount_pct"].corr(df["quantity"])), 4),
        "by_depth": by_depth,
    }


def run_promo_diagnostics(df: pd.DataFrame) -> dict[str, Any]:
    """Run every diagnostic and return the results in one dict."""
    return {
        "sparsity": panel_sparsity(df),
        "assignment": promo_assignment_profile(df),
        "persistence": promo_persistence(df),
        "demand_response": demand_response(df),
        "promo_share_pct": round(float(df["is_promo"].mean() * 100), 1),
    }
