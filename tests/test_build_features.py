"""Unit tests for src.features.build_features."""

from __future__ import annotations

from src.data.cleaning import clean_fact_sales
from src.features.build_features import build_sales_analysis_table


def test_analysis_table_excludes_invalid_and_returns_by_default(
    raw_fact_sales, dim_customer, dim_product, dim_store, dim_date
):
    cleaned, _ = clean_fact_sales(
        raw_fact_sales, dim_customer, dim_product, dim_store, dim_date
    )
    analysis = build_sales_analysis_table(cleaned, dim_customer, dim_store, dim_date)

    # T004 (bad product), T005 (bad store), T006 (zero qty), T007 (return),
    # T008 (bad price), T009 (bad date) should ALL be excluded by default.
    excluded_ids = {"T004", "T005", "T006", "T007", "T008", "T009"}
    assert not excluded_ids & set(analysis["transaction_id"])
    assert {"T001", "T003", "T010"} <= set(analysis["transaction_id"])


def test_analysis_table_can_include_returns(
    raw_fact_sales, dim_customer, dim_product, dim_store, dim_date
):
    cleaned, _ = clean_fact_sales(
        raw_fact_sales, dim_customer, dim_product, dim_store, dim_date
    )
    analysis = build_sales_analysis_table(
        cleaned, dim_customer, dim_store, dim_date, include_returns=True
    )
    assert "T007" in set(analysis["transaction_id"])


def test_is_promo_and_discount_pct(
    raw_fact_sales, dim_customer, dim_product, dim_store, dim_date
):
    cleaned, _ = clean_fact_sales(
        raw_fact_sales, dim_customer, dim_product, dim_store, dim_date
    )
    analysis = build_sales_analysis_table(cleaned, dim_customer, dim_store, dim_date)

    t001 = analysis[analysis["transaction_id"] == "T001"].iloc[0]  # no discount
    assert not t001["is_promo"]
    assert t001["discount_pct"] == 0.0

    t003 = analysis[analysis["transaction_id"] == "T003"].iloc[
        0
    ]  # discount=30 on gross=300
    assert t003["is_promo"]
    assert abs(t003["discount_pct"] - 0.10) < 1e-9


def test_analysis_table_joins_store_and_customer_attributes(
    raw_fact_sales, dim_customer, dim_product, dim_store, dim_date
):
    cleaned, _ = clean_fact_sales(
        raw_fact_sales, dim_customer, dim_product, dim_store, dim_date
    )
    analysis = build_sales_analysis_table(cleaned, dim_customer, dim_store, dim_date)
    t001 = analysis[analysis["transaction_id"] == "T001"].iloc[0]
    assert t001["region"] == "Central"  # S01 -> Central
    assert t001["customer_segment"] == "Premium"  # C001 -> Premium
