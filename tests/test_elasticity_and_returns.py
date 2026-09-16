"""Unit tests for src.analysis.elasticity and src.analysis.returns."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.analysis.elasticity import compute_price_elasticity
from src.analysis.returns import compute_return_rate
from src.data.cleaning import clean_fact_sales


def test_elasticity_recovers_known_slope_from_synthetic_log_log_data():
    """Q = 100000 * P^-2 is an EXACT log-log relationship with elasticity
    -2.0 by construction. A correct regression should recover it closely."""
    n_days = 20
    prices = np.linspace(10, 30, n_days)
    true_elasticity = -2.0
    units = 100_000 * prices**true_elasticity

    df = pd.DataFrame(
        {
            "product_id": ["P001"] * n_days,
            "transaction_date": pd.date_range("2024-01-01", periods=n_days, freq="D"),
            "unit_price": prices,
            "quantity": units.round().astype(int),
        }
    )
    result = compute_price_elasticity(df, ["product_id"])
    row = result.iloc[0]
    assert np.isclose(row["elasticity"], true_elasticity, atol=0.05)
    assert row["r_squared"] > 0.99
    assert row["interpretation"] == "elastic (price-sensitive)"


def test_elasticity_excludes_skus_with_insufficient_days():
    """Only 5 days of data -- below MIN_DAYS_WITH_SALES=15 -- should be skipped entirely."""
    df = pd.DataFrame(
        {
            "product_id": ["P001"] * 5,
            "transaction_date": pd.date_range("2024-01-01", periods=5, freq="D"),
            "unit_price": [10, 12, 14, 16, 18],
            "quantity": [100, 90, 85, 80, 75],
        }
    )
    result = compute_price_elasticity(df, ["product_id"])
    assert result.empty


def test_elasticity_excludes_skus_with_no_price_variation():
    """A flat price (no variation at all) gives nothing to regress against."""
    df = pd.DataFrame(
        {
            "product_id": ["P001"] * 20,
            "transaction_date": pd.date_range("2024-01-01", periods=20, freq="D"),
            "unit_price": [50.0] * 20,
            "quantity": np.random.default_rng(0).integers(80, 120, 20),
        }
    )
    result = compute_price_elasticity(df, ["product_id"])
    assert result.empty


def test_return_rate_computation(
    raw_fact_sales, dim_customer, dim_product, dim_store, dim_date
):
    cleaned, _ = clean_fact_sales(
        raw_fact_sales, dim_customer, dim_product, dim_store, dim_date
    )
    result = compute_return_rate(cleaned, ["category"])
    # Electronics (P001): T001 qty=2, T003 qty=3, T011 qty=1 sold = 6 units sold;
    # T007 qty=-1 is the one return = 1 returned unit -> rate = 1/6*100 = 16.67%
    row = result[result["category"] == "Electronics"].iloc[0]
    assert row["gross_units_sold"] == 6
    assert row["returned_units"] == 1
    assert np.isclose(row["return_rate_pct"], 1 / 6 * 100, atol=0.01)
