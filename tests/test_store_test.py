"""Unit tests for src.analysis.store_test."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.analysis.store_test import analyze_store_test, assign_stores, store_week_table


def _stores(n: int = 8) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "store_id": [f"S{i:02d}" for i in range(n)],
            "region": ["East" if i < n // 2 else "West" for i in range(n)],
            "store_type": ["Mall" if i % 2 == 0 else "Hyper" for i in range(n)],
        }
    )


def _panel(assignment: pd.DataFrame, txn_effect: float, weeks: int = 16, seed: int = 0) -> pd.DataFrame:
    """Transactions ~ Poisson(60), x (1 + effect) in capped stores. Profit is 1,400 per transaction."""
    rng = np.random.default_rng(seed)
    rows = []
    for _, a in assignment.iterrows():
        mean = 60 * (1 + txn_effect) if a["arm"] == "cap" else 60
        for w in range(weeks):
            txns = rng.poisson(mean)
            rows.append(
                {
                    "store_id": a["store_id"],
                    "week": pd.Timestamp("2025-01-06") + pd.Timedelta(weeks=w),
                    "txns": txns,
                    "profit": 1400.0 * txns,
                    "above_cap_share": 0.0 if a["arm"] == "cap" else 0.12,
                }
            )
    return pd.DataFrame(rows)


def test_assignment_pairs_stores_and_caps_exactly_one_per_pair():
    result = assign_stores(_stores(), seed=1)
    assert len(result) == 8
    assert result.groupby("pair_id")["arm"].apply(lambda s: sorted(s)).eq([["cap", "control"]] * 4).all()
    regions = _stores().set_index("store_id")["region"]
    for _, pair in result.groupby("pair_id"):
        assert regions[pair["store_id"]].nunique() == 1  # pairs never mix regions here


def test_assignment_is_reproducible_and_depends_on_the_seed():
    first, again = assign_stores(_stores(), seed=7), assign_stores(_stores(), seed=7)
    assert first.equals(again)
    arms = {tuple(assign_stores(_stores(), seed=s)["arm"]) for s in range(10)}
    assert len(arms) > 1


def test_assignment_needs_an_even_number_of_stores():
    with pytest.raises(ValueError, match="even number"):
        assign_stores(_stores(7), seed=0)


def test_no_effect_is_safe_and_close_to_zero():
    assignment = assign_stores(_stores(20), seed=2)
    result = analyze_store_test(_panel(assignment, 0.0), assignment)
    assert abs(result["transactions"]["change_pct"]) < 3
    assert result["verdict"] == "safe"
    assert result["above_cap_share_pct"] == {"cap": 0.0, "control": 12.0}


def test_a_large_traffic_loss_is_harmful():
    assignment = assign_stores(_stores(20), seed=3)
    result = analyze_store_test(_panel(assignment, -0.15), assignment)
    assert result["transactions"]["ci_high_pct"] < -3.5
    assert result["verdict"] == "harmful"


def test_a_short_noisy_test_is_inconclusive():
    assignment = assign_stores(_stores(8), seed=4)
    result = analyze_store_test(_panel(assignment, -0.035, weeks=3), assignment)
    assert result["verdict"] == "inconclusive"


def test_missing_weeks_are_rejected():
    assignment = assign_stores(_stores(8), seed=5)
    with pytest.raises(ValueError, match="every week"):
        analyze_store_test(_panel(assignment, 0.0).iloc[:-1], assignment)


def test_store_week_table_counts_transactions_profit_and_sales_above_the_cap():
    analysis = pd.DataFrame(
        {
            "store_id": ["S1", "S1", "S1", "S2"],
            "date": pd.to_datetime(["2025-01-06", "2025-01-07", "2025-01-14", "2025-01-06"]),
            "quantity": [1, 2, 1, 1],
            "profit_amount": [10.0, 20.0, 30.0, 40.0],
            "discount_pct": [0.20, 0.10, 0.0, 0.15],
        }
    )
    table = store_week_table(analysis).set_index(["store_id", "week"])
    first = table.loc[("S1", pd.Timestamp("2025-01-06"))]
    assert first["txns"] == 2 and first["profit"] == 30.0
    assert first["above_cap_share"] == 0.5  # the 20% sale is above the 10% cap, the 10% sale is not
    assert table.loc[("S2", pd.Timestamp("2025-01-06")), "above_cap_share"] == 1.0
