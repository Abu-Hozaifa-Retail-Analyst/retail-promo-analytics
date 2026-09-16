"""Unit tests for src.utils.parallel.run_grouped_parallel."""

from __future__ import annotations

import pandas as pd

from src.utils.parallel import run_grouped_parallel


def test_single_group_column_key_is_correct_type():
    df = pd.DataFrame({"sku": ["A", "A", "B", "B"], "value": [1, 2, 3, 4]})
    result = run_grouped_parallel(
        df, "sku", lambda g: {"total": g["value"].sum()}, n_jobs=1
    )
    assert set(result["sku"]) == {"A", "B"}
    assert result[result["sku"] == "A"]["total"].iloc[0] == 3


def test_multi_group_columns():
    df = pd.DataFrame(
        {"sku": ["A", "A", "B"], "store": ["S1", "S2", "S1"], "value": [10, 20, 30]}
    )
    result = run_grouped_parallel(
        df, ["sku", "store"], lambda g: {"total": g["value"].sum()}, n_jobs=1
    )
    assert len(result) == 3
    row = result[(result["sku"] == "A") & (result["store"] == "S1")]
    assert row["total"].iloc[0] == 10


def test_fn_returning_none_is_excluded():
    df = pd.DataFrame({"sku": ["A", "A", "B"], "value": [1, 2, 3]})

    def fn(g):
        return None if g["sku"].iloc[0] == "B" else {"total": g["value"].sum()}

    result = run_grouped_parallel(df, "sku", fn, n_jobs=1)
    assert set(result["sku"]) == {"A"}


def test_min_group_size_filters_small_groups():
    df = pd.DataFrame({"sku": ["A", "A", "A", "B"], "value": [1, 2, 3, 4]})
    result = run_grouped_parallel(
        df, "sku", lambda g: {"total": g["value"].sum()}, n_jobs=1, min_group_size=2
    )
    assert set(result["sku"]) == {"A"}
