"""Unit tests for src.analysis.pooled_elasticity."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.analysis.pooled_elasticity import estimate_pooled_elasticity


def _synthetic(true_elasticity: float, n_skus: int = 100, n_per_sku: int = 60, seed: int = 0) -> pd.DataFrame:
    """Quantity generated from a KNOWN elasticity, plus a different baseline per SKU."""
    rng = np.random.default_rng(seed)
    rows = []
    for sku in range(n_skus):
        base = rng.uniform(1.0, 3.0)  # SKU-specific demand level (the SKU fixed effect)
        disc = rng.choice([0.0, 0.05, 0.10, 0.20], size=n_per_sku)
        noise = rng.normal(0, 0.05, size=n_per_sku)
        qty = np.exp(base + true_elasticity * np.log(1 - disc) + noise)
        rows.append(pd.DataFrame({"product_id": f"P{sku}", "discount_pct": disc, "quantity": qty}))
    return pd.concat(rows, ignore_index=True)


def _confounded(true_elasticity: float, seed: int = 0) -> pd.DataFrame:
    """Busy weeks have BOTH higher demand and more discounting.

    This is the classic trap: discounts and demand rise together for reasons
    unrelated to the discount, so low prices and high quantities appear
    together and a naive estimate makes demand look MORE price-sensitive
    than it really is.
    """
    rng = np.random.default_rng(seed)
    n_weeks, n_skus, per_cell = 30, 40, 4
    week_shock = rng.normal(0, 0.6, size=n_weeks)
    sku_base = rng.uniform(1.0, 3.0, size=n_skus)
    rows = []
    for w in range(n_weeks):
        p_disc = 1 / (1 + np.exp(-4 * week_shock[w]))  # busier week -> more discounting
        for s in range(n_skus):
            disc = np.where(rng.random(per_cell) < p_disc, 0.20, 0.0)
            noise = rng.normal(0, 0.05, size=per_cell)
            qty = np.exp(sku_base[s] + week_shock[w] + true_elasticity * np.log(1 - disc) + noise)
            rows.append(
                pd.DataFrame(
                    {"product_id": f"P{s}", "week": f"W{w}", "discount_pct": disc, "quantity": qty}
                )
            )
    return pd.concat(rows, ignore_index=True)


def test_recovers_known_elasticity_despite_different_sku_baselines():
    result = estimate_pooled_elasticity(_synthetic(-2.0))
    assert abs(result["elasticity"] - (-2.0)) < 0.05
    assert result["n_clusters"] == 100


def test_zero_response_is_estimated_near_zero_and_flagged_inelastic():
    result = estimate_pooled_elasticity(_synthetic(0.0))
    assert abs(result["elasticity"]) < 0.05
    assert result["elastic_rejected"]  # clearly NOT as elastic as -1


def test_strong_response_is_not_flagged_as_inelastic():
    result = estimate_pooled_elasticity(_synthetic(-2.0))
    assert not result["elastic_rejected"]


def test_week_fixed_effects_remove_seasonal_confounding():
    df = _confounded(-1.0)
    naive = estimate_pooled_elasticity(df, fixed_effects=("product_id",))
    controlled = estimate_pooled_elasticity(df, fixed_effects=("product_id", "week"))
    assert abs(naive["elasticity"] - (-1.0)) > 1.0  # naive estimate is badly off (about -3.6)
    assert abs(controlled["elasticity"] - (-1.0)) < 0.1  # week effects recover the truth
