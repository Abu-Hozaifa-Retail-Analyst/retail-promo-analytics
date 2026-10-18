"""Unit tests for src.analysis.returns."""

from __future__ import annotations

import numpy as np

from src.analysis.returns import compute_return_rate
from src.data.cleaning import clean_fact_sales


def test_return_rate_computation(raw_fact_sales, dim_customer, dim_product, dim_store, dim_date):
    cleaned, _ = clean_fact_sales(raw_fact_sales, dim_customer, dim_product, dim_store, dim_date)
    result = compute_return_rate(cleaned, ["category"])
    # Electronics (P001): T001 qty=2, T003 qty=3, T011 qty=1 sold = 6 units sold;
    # T007 qty=-1 is the one return = 1 returned unit -> rate = 1/6*100 = 16.67%
    row = result[result["category"] == "Electronics"].iloc[0]
    assert row["gross_units_sold"] == 6
    assert row["returned_units"] == 1
    assert np.isclose(row["return_rate_pct"], 1 / 6 * 100, atol=0.01)
