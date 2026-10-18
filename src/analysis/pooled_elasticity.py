"""Pooled price elasticity with fixed effects and cluster-robust errors.

Why pooled instead of one regression per SKU: each SKU has only ~240
transactions, so per-SKU slopes are mostly noise (the distribution of
per-SKU estimates in the original analysis was centred on zero with a
huge spread). Pooling all SKUs while giving each its own intercept
("fixed effect") uses all ~118K transactions to estimate ONE precise
elasticity, with uncertainty that is honest about SKU-level clustering.

Model:  log(quantity) = SKU effect [+ week effect] + elasticity * log(1 - discount) + error
"""

from __future__ import annotations

from collections.abc import Sequence
from functools import partial

import numpy as np
import pandas as pd

from src.utils.parallel import run_grouped_parallel


def _demean(
    values: pd.Series,
    groups: Sequence[np.ndarray],
    max_iter: int = 100,
    tol: float = 1e-10,
) -> np.ndarray:
    """Remove group means from `values`, for one or several sets of groups.

    With a single set of groups one pass is exact. With several (e.g. SKU
    and week) we alternate between them until the result stops changing.
    """
    x = values.to_numpy(dtype=float).copy()
    for _ in range(max_iter):
        previous = x.copy()
        for g in groups:
            x = x - pd.Series(x).groupby(g).transform("mean").to_numpy()
        if np.max(np.abs(x - previous)) < tol:
            break
    return x


def estimate_pooled_elasticity(
    df: pd.DataFrame,
    fixed_effects: Sequence[str] = ("product_id",),
    cluster: str = "product_id",
) -> dict:
    """Estimate one price elasticity of demand across all rows of `df`.

    Args:
        df: Analysis table with `quantity`, `discount_pct`, and the columns
            named in `fixed_effects` and `cluster`.
        fixed_effects: Columns whose group means are absorbed (e.g. SKU,
            or SKU plus a year-week key to control for seasonality).
        cluster: Column defining independent clusters for the standard error.

    Returns:
        Dict with the elasticity, its standard error and 95% interval,
        sample sizes, and `elastic_rejected` (True when even the lower end
        of the interval is above -1, i.e. demand is clearly inelastic).
    """
    d = df[(df["discount_pct"] < 0.99) & (df["quantity"] > 0)]
    y = np.log(d["quantity"])
    x = np.log(1 - d["discount_pct"])  # log of price relative to list price

    groups = [d[c].to_numpy() for c in fixed_effects]
    y_t, x_t = _demean(y, groups), _demean(x, groups)

    sxx = float(np.sum(x_t**2))
    beta = float(np.sum(x_t * y_t) / sxx)
    resid = y_t - beta * x_t

    # Cluster-robust variance: sum the score within each cluster first, so
    # correlated errors inside a SKU are not treated as independent evidence.
    scores = pd.Series(x_t * resid).groupby(d[cluster].to_numpy()).sum()
    n_clusters = len(scores)
    var = float(np.sum(scores**2)) / sxx**2 * n_clusters / (n_clusters - 1)
    se = float(np.sqrt(var))

    return {
        "elasticity": round(beta, 3),
        "std_error": round(se, 3),
        "ci_low": round(beta - 1.96 * se, 3),
        "ci_high": round(beta + 1.96 * se, 3),
        "n_obs": int(len(d)),
        "n_clusters": int(n_clusters),
        "elastic_rejected": bool(beta - 1.96 * se > -1.0),
    }


def pooled_elasticity_by_group(
    df: pd.DataFrame,
    group_col: str,
    fixed_effects: Sequence[str] = ("product_id",),
    n_jobs: int = -1,
) -> pd.DataFrame:
    """Run the pooled estimate separately inside each group (e.g. category).

    Each group's regression is independent, so they run in parallel.
    """
    return run_grouped_parallel(
        df,
        group_col,
        partial(estimate_pooled_elasticity, fixed_effects=fixed_effects),
        n_jobs=n_jobs,
        min_group_size=500,
    )
