"""Discount-cap scenarios: what happens to profit if no discount may exceed a cap?

A cap of c leaves every sale discounted at or below c untouched. A sale
discounted at depth d > c is re-priced from P*(1-d) to P*(1-c), and its volume
reacts with a constant price elasticity e (negative: higher price, fewer units):

    volume multiplier = ((1 - c) / (1 - d)) ** e

Why elasticity is a parameter and not a fixed input: the pooled estimate from
this data (about -0.003) only covers basket size per transaction. It cannot see
customers who stop coming at all, so conclusions are shown across a range of
elasticities, plus the break-even elasticity at which a cap stops paying.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import brentq

from src.analysis.breakeven import nominal_depth

DEFAULT_CAPS = (0.0, 0.05, 0.10, 0.15)
DEFAULT_ELASTICITIES = (0.0, -0.05, -0.5, -1.0, -2.0, -3.0)


def _simulate(df: pd.DataFrame, cap: float, elasticity: float) -> dict[str, float]:
    """Unrounded scenario totals (kept separate so the solver sees a smooth function)."""
    gross = df["gross_sales"].to_numpy(dtype=float)
    cost = df["cost_amount"].to_numpy(dtype=float)
    discount = df["discount_amount"].to_numpy(dtype=float)
    qty = df["quantity"].to_numpy(dtype=float)

    depth = np.divide(discount, gross, out=np.zeros_like(gross), where=gross > 0)
    depth = np.clip(depth, 0.0, 0.9999)
    affected = df["is_promo"].to_numpy() & (nominal_depth(pd.Series(depth)).to_numpy() > cap + 1e-9)

    new_discount = np.where(affected, gross * cap, discount)
    ratio = np.where(affected, (1 - cap) / (1 - depth), 1.0)
    mult = ratio**elasticity

    old_net = gross - discount
    new_net = mult * (gross - new_discount)
    new_profit = new_net - mult * cost
    old_profit = old_net - cost
    return {
        "affected": float(affected.sum()),
        "profit_change": float(new_profit.sum() - old_profit.sum()),
        "net_sales_change": float(new_net.sum() - old_net.sum()),
        "units_change": float(((mult - 1) * qty).sum()),
        "old_profit": float(old_profit.sum()),
        "total_units": float(qty.sum()),
    }


def simulate_discount_cap(df: pd.DataFrame, cap: float, elasticity: float) -> dict[str, Any]:
    """Profit, sales and unit change if discounts were capped at `cap`.

    Args:
        df: Analysis table (valid, non-return rows) with `is_promo`, `gross_sales`,
            `cost_amount`, `discount_amount` and `quantity`.
        cap: Maximum allowed discount as a fraction (0.10 = 10%). 0.0 removes all discounts.
        elasticity: Price elasticity of volume for the re-priced sales (zero or negative).
    """
    r = _simulate(df, cap, elasticity)
    n_promo = int(df["is_promo"].sum())
    return {
        "cap": cap,
        "elasticity": elasticity,
        "txns_affected": int(r["affected"]),
        "share_of_promo_txns_affected_pct": round(r["affected"] / n_promo * 100, 1),
        "profit_change": round(r["profit_change"]),
        "profit_change_pct": round(r["profit_change"] / r["old_profit"] * 100, 1),
        "net_sales_change": round(r["net_sales_change"]),
        "units_change_pct": round(r["units_change"] / r["total_units"] * 100, 1),
    }


def scenario_grid(
    df: pd.DataFrame,
    caps: Sequence[float] = DEFAULT_CAPS,
    elasticities: Sequence[float] = DEFAULT_ELASTICITIES,
) -> pd.DataFrame:
    """Run every (cap, elasticity) combination and return one row per scenario."""
    return pd.DataFrame([simulate_discount_cap(df, c, e) for c in caps for e in elasticities])


def breakeven_elasticity(df: pd.DataFrame, cap: float, lower: float = -50.0) -> float:
    """The elasticity at which capping discounts changes profit by exactly zero.

    Capping pays whenever demand is LESS price-sensitive than this value (for
    example, a break-even of -4.3 means capping pays unless the elasticity is
    stronger than -4.3). Returns `-inf` if capping still pays at `lower`.
    """

    def profit_change(e: float) -> float:
        return _simulate(df, cap, e)["profit_change"]

    if profit_change(0.0) <= 0:
        return 0.0
    if profit_change(lower) > 0:
        return float("-inf")
    return float(brentq(profit_change, lower, 0.0, xtol=1e-6))
