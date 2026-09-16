"""Unit tests for promo_lift, margin_erosion, and promo_ranking."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.analysis.margin_erosion import compute_margin_erosion
from src.analysis.promo_lift import compute_promo_lift
from src.analysis.promo_ranking import rank_promotions


def _make_lift_fixture() -> pd.DataFrame:
    """3 non-promo days at 10 units/1000 revenue/300 profit per day,
    3 promo days at 15 units (+50%)/1200 revenue (+20%)/200 profit per day."""
    rows = []
    for d in pd.date_range("2024-01-01", periods=3, freq="D"):
        rows.append(
            dict(
                product_id="P001",
                transaction_date=d,
                is_promo=False,
                quantity=10,
                net_sales=1000.0,
                profit_amount=300.0,
                discount_amount=0.0,
            )
        )
    for d in pd.date_range("2024-02-01", periods=3, freq="D"):
        rows.append(
            dict(
                product_id="P001",
                transaction_date=d,
                is_promo=True,
                quantity=15,
                net_sales=1200.0,
                profit_amount=200.0,
                discount_amount=150.0,
            )
        )
    return pd.DataFrame(rows)


def test_promo_lift_unit_and_revenue_lift_pct():
    df = _make_lift_fixture()
    row = compute_promo_lift(df, ["product_id"]).iloc[0]
    assert row["unit_lift_pct"] == 50.0
    assert row["revenue_lift_pct"] == 20.0


def test_margin_erosion_and_incremental_profit():
    df = _make_lift_fixture()
    row = compute_margin_erosion(df, ["product_id"]).iloc[0]
    # margin_pct nonpromo = 300/1000*100 = 30; promo = 200/1200*100 = 16.67
    assert np.isclose(row["avg_margin_pct_nonpromo"], 30.0)
    assert row["margin_erosion_pts"] > 0
    # incremental profit = (200 - 300) * 3 promo days = -300 (this promo LOST money)
    assert np.isclose(row["incremental_profit_vs_baseline"], -300.0)
    assert not row["promo_profitable"]


def test_rank_promotions_best_and_worst_identify_correct_groups():
    df_p1 = _make_lift_fixture()  # P001: unprofitable promo

    rows = []  # P002: a genuinely profitable promo
    for d in pd.date_range("2024-01-01", periods=3, freq="D"):
        rows.append(
            dict(
                product_id="P002",
                transaction_date=d,
                is_promo=False,
                quantity=10,
                net_sales=1000.0,
                profit_amount=300.0,
                discount_amount=0.0,
            )
        )
    for d in pd.date_range("2024-02-01", periods=3, freq="D"):
        rows.append(
            dict(
                product_id="P002",
                transaction_date=d,
                is_promo=True,
                quantity=40,
                net_sales=3500.0,
                profit_amount=900.0,
                discount_amount=100.0,
            )
        )
    df_p2 = pd.DataFrame(rows)

    combined = pd.concat([df_p1, df_p2], ignore_index=True)
    result = rank_promotions(combined, ["product_id"], top_n=1)

    assert result["best"]["product_id"].iloc[0] == "P002"
    assert result["best"]["promo_profitable"].iloc[0]
    assert result["worst"]["product_id"].iloc[0] == "P001"
    assert not result["worst"]["promo_profitable"].iloc[0]
