"""Unit tests for src.analysis.breakeven, using frames small enough to check by hand."""

from __future__ import annotations

import math

import pandas as pd

from src.analysis.breakeven import breakeven_table, discount_cost_summary, nominal_depth


def _row(
    promo: bool, gross: float, cost: float, discount: float, qty: int = 1, **extra
) -> dict:
    net = gross - discount
    return {
        "is_promo": promo,
        "gross_sales": gross,
        "cost_amount": cost,
        "discount_amount": discount,
        "net_sales": net,
        "profit_amount": net - cost,
        "discount_pct": discount / gross,
        "quantity": qty,
        **extra,
    }


def test_nominal_depth_snaps_cent_rounding_to_the_real_discount_level():
    snapped = nominal_depth(pd.Series([0.0499, 0.0501, 0.1498, 0.2003]))
    assert snapped.tolist() == [0.05, 0.05, 0.15, 0.20]


def test_required_lift_matches_the_textbook_formula():
    # Margin at list = 30%, discount = 10%  ->  required lift = 0.10 / (0.30 - 0.10) = 50%
    df = pd.DataFrame(
        [
            _row(True, 100, 70, 10),
            _row(True, 100, 70, 10),
            _row(False, 100, 70, 0),
            _row(False, 100, 70, 0),
        ]
    )
    row = breakeven_table(df).iloc[0]
    assert row["depth"] == 0.10
    assert row["full_price_margin_pct"] == 30.0
    assert row["required_volume_lift_pct"] == 50.0


def test_discount_deeper_than_margin_can_never_break_even():
    # Margin 20%, discount 30%: each sale loses money, no volume lift can fix that.
    df = pd.DataFrame(
        [
            _row(True, 100, 80, 30),
            _row(True, 100, 80, 30),
            _row(False, 100, 80, 0),
            _row(False, 100, 80, 0),
        ]
    )
    row = breakeven_table(df).iloc[0]
    assert math.isinf(row["required_volume_lift_pct"])
    assert row["below_cost_txns"] == 2
    assert row["below_cost_share_pct"] == 100.0


def test_observed_lift_and_extra_traffic_needed():
    # Promo baskets are twice as big as non-promo (+100%), but only +50% is needed to break even,
    # so the discount more than pays for itself: extra transactions needed = 1.5 / 2.0 - 1 = -25%.
    df = pd.DataFrame(
        [
            _row(True, 100, 70, 10, qty=4),
            _row(True, 100, 70, 10, qty=4),
            _row(False, 100, 70, 0, qty=2),
            _row(False, 100, 70, 0, qty=2),
        ]
    )
    row = breakeven_table(df).iloc[0]
    assert row["observed_qty_lift_pct"] == 100.0
    assert row["extra_txn_growth_needed_pct"] == -25.0


def test_group_cols_evaluate_each_group_against_its_own_margin():
    # Same 10% discount: category X has a 30% margin (needs +50%), Y has a 50% margin (needs +25%).
    rows = []
    for cat, cost in [("X", 70), ("Y", 50)]:
        rows += [
            _row(True, 100, cost, 10, category=cat),
            _row(True, 100, cost, 10, category=cat),
            _row(False, 100, cost, 0, category=cat),
            _row(False, 100, cost, 0, category=cat),
        ]
    result = breakeven_table(pd.DataFrame(rows), ["category"]).set_index("category")
    assert result.loc["X", "required_volume_lift_pct"] == 50.0
    assert result.loc["Y", "required_volume_lift_pct"] == 25.0


def test_discount_cost_summary_totals():
    # Two promo sales (profit 20 each, 10 discount each) and one full-price sale (profit 30).
    df = pd.DataFrame(
        [_row(True, 100, 70, 10), _row(True, 100, 70, 10), _row(False, 100, 70, 0)]
    )
    s = discount_cost_summary(df)
    assert s["promo_txns"] == 2
    assert s["promo_share_pct"] == 66.7
    assert s["total_discount_given"] == 20
    assert s["total_profit"] == 70
    assert s["discount_pct_of_profit"] == 28.6  # 20 / 70
    assert s["profit_if_no_discounts_same_volume"] == 90
    assert (
        s["max_tolerable_volume_loss_pct"] == 33.3
    )  # 20 / (40 promo profit + 20 discount)
    assert s["below_cost_txns"] == 0
