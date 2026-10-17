"""Unit tests for src.analysis.scenarios, using one-row frames whose answers can be checked by hand."""

from __future__ import annotations

import math

import pandas as pd

from src.analysis.scenarios import (
    breakeven_elasticity,
    scenario_grid,
    simulate_discount_cap,
)


def _row(promo: bool, gross: float, cost: float, discount: float, qty: int = 1) -> dict:
    return {
        "is_promo": promo,
        "gross_sales": gross,
        "cost_amount": cost,
        "discount_amount": discount,
        "quantity": qty,
    }


def test_no_demand_response_gains_exactly_the_discount_removed():
    # A 20% discount capped at 10% with no volume change: price rises by 10, so profit rises by 10.
    df = pd.DataFrame([_row(True, 100, 70, 20)])
    result = simulate_discount_cap(df, cap=0.10, elasticity=0.0)
    assert result["profit_change"] == 10
    assert result["net_sales_change"] == 10
    assert result["units_change_pct"] == 0.0


def test_sales_at_or_below_the_cap_and_full_price_sales_are_untouched():
    df = pd.DataFrame([_row(True, 100, 70, 5), _row(False, 100, 70, 0)])
    result = simulate_discount_cap(df, cap=0.10, elasticity=-1.0)
    assert result["txns_affected"] == 0
    assert result["profit_change"] == 0


def test_volume_reacts_to_the_price_increase():
    # 20% -> 10% cap, elasticity -1: volume multiplier = (0.9 / 0.8) ** -1 = 0.8889
    # old profit = 800 - 700 = 100; new profit = 0.8889 * (900 - 700) = 177.78; change = +78
    df = pd.DataFrame([_row(True, 1000, 700, 200)])
    result = simulate_discount_cap(df, cap=0.10, elasticity=-1.0)
    assert result["profit_change"] == 78
    assert result["units_change_pct"] == -11.1


def test_unit_elasticity_leaves_net_sales_unchanged():
    # With elasticity -1, the price rise and the volume fall cancel exactly.
    df = pd.DataFrame([_row(True, 1000, 700, 200)])
    result = simulate_discount_cap(df, cap=0.10, elasticity=-1.0)
    assert result["net_sales_change"] == 0


def test_cap_of_zero_removes_every_discount():
    df = pd.DataFrame([_row(True, 100, 70, 10), _row(True, 100, 70, 20)])
    result = simulate_discount_cap(df, cap=0.0, elasticity=0.0)
    assert result["txns_affected"] == 2
    assert result["profit_change"] == 30


def test_breakeven_elasticity_matches_the_closed_form():
    # Profit is unchanged when volume multiplier * 20 = 10, i.e. (0.9/0.8) ** e = 0.5,
    # so e = ln(0.5) / ln(1.125).
    df = pd.DataFrame([_row(True, 100, 70, 20)])
    expected = math.log(0.5) / math.log(0.9 / 0.8)
    assert abs(breakeven_elasticity(df, cap=0.10) - expected) < 0.01


def test_breakeven_elasticity_is_zero_when_there_is_nothing_to_cap():
    df = pd.DataFrame([_row(True, 100, 70, 5)])
    assert breakeven_elasticity(df, cap=0.10) == 0.0


def test_scenario_grid_has_one_row_per_cap_and_elasticity():
    df = pd.DataFrame([_row(True, 100, 70, 20), _row(False, 100, 70, 0)])
    grid = scenario_grid(df, caps=(0.0, 0.10), elasticities=(0.0, -1.0, -2.0))
    assert len(grid) == 6
    assert set(grid["cap"]) == {0.0, 0.10}
