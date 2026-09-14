"""Thin wrapper around joblib for parallelizing independent per-group work."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pandas as pd
from joblib import Parallel, delayed


def run_grouped_parallel(
    df: pd.DataFrame,
    group_cols: str | list[str],
    fn: Callable[[pd.DataFrame], dict[str, Any] | None],
    *,
    n_jobs: int = -1,
    min_group_size: int = 1,
) -> pd.DataFrame:
    """Apply `fn` to each group of `df` independently, in parallel."""
    if isinstance(group_cols, str):
        group_cols = [group_cols]

    groups = df.groupby(group_cols)
    eligible = [(key, g) for key, g in groups if len(g) >= min_group_size]

    results = Parallel(n_jobs=n_jobs)(delayed(fn)(g) for _, g in eligible)

    rows = []
    for (key, _), result in zip(eligible, results):
        if result is None:
            continue
        key_tuple = key if isinstance(key, tuple) else (key,)
        row = dict(zip(group_cols, key_tuple))
        row.update(result)
        rows.append(row)

    return pd.DataFrame(rows)
