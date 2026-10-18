"""Unit tests for src.analysis.diagnostics, using tiny hand-checkable frames."""

from __future__ import annotations

import pandas as pd

from src.analysis.diagnostics import (
    demand_response,
    panel_sparsity,
    promo_assignment_profile,
    promo_persistence,
)


def test_panel_sparsity_counts_empty_sku_days():
    # 2 SKUs x 4 days = 8 cells. Sales exist in only 3 cells:
    # (A, Jan 1), (A, Jan 2 - two transactions), (B, Jan 1)
    df = pd.DataFrame(
        {
            "product_id": ["A", "A", "A", "B"],
            "transaction_date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-02", "2024-01-01"]),
        }
    )
    result = panel_sparsity(df, n_days=4)
    assert result["sku_days_total"] == 8
    assert result["sku_days_with_sales"] == 3
    assert result["pct_sku_days_with_sales"] == 37.5
    assert result["pct_sku_days_zero_sales"] == 62.5
    assert result["avg_txns_per_active_sku_day"] == 1.33  # 4 transactions / 3 cells


def test_promo_assignment_profile_spread():
    df = pd.DataFrame(
        {
            "category": ["X", "X", "Y", "Y"],
            "is_promo": [True, False, True, True],  # X: 50%, Y: 100%
        }
    )
    row = promo_assignment_profile(df, ["category"]).iloc[0]
    assert row["min_promo_share_pct"] == 50.0
    assert row["max_promo_share_pct"] == 100.0
    assert row["spread_pts"] == 50.0


def test_promo_persistence_detects_sticky_promos():
    # One SKU, promo flags in time order: T, T, F, F, F
    # After a promo txn: next is T then F  -> 0.5
    # After a non-promo txn: next is F then F -> 0.0
    df = pd.DataFrame(
        {
            "product_id": ["A"] * 5,
            "transaction_date": pd.date_range("2024-01-01", periods=5),
            "is_promo": [True, True, False, False, False],
        }
    )
    result = promo_persistence(df)
    assert result["p_promo_after_promo"] == 0.5
    assert result["p_promo_after_nonpromo"] == 0.0
    assert result["gap"] == 0.5


def _demand_frame(promo_qty: list[int], nonpromo_qty: list[int]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "is_promo": [True] * len(promo_qty) + [False] * len(nonpromo_qty),
            "quantity": promo_qty + nonpromo_qty,
            "discount_pct": [0.1] * len(promo_qty) + [0.0] * len(nonpromo_qty),
            "promo_depth_bucket": ["5-15%"] * len(promo_qty) + ["No Promo"] * len(nonpromo_qty),
            "profit_amount": [10.0] * len(promo_qty) + [20.0] * len(nonpromo_qty),
            "gross_margin_pct": [15.0] * len(promo_qty) + [25.0] * len(nonpromo_qty),
        }
    )


def test_demand_response_zero_lift_when_quantity_is_unchanged():
    # Same quantities in both groups (mean 3 each), with real variation so the
    # discount/quantity correlation is well-defined.
    result = demand_response(_demand_frame([2, 4], [2, 4]))
    assert result["qty_lift_pct"] == 0.0
    assert result["corr_discount_qty"] == 0.0


def test_demand_response_detects_real_lift():
    result = demand_response(_demand_frame([6, 6], [3, 3]))
    assert result["qty_lift_pct"] == 100.0
    assert set(result["by_depth"].index) == {"5-15%", "No Promo"}
