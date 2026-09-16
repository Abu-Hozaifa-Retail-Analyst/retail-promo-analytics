"""Unit tests for src.data.cleaning.clean_fact_sales."""

from __future__ import annotations

import numpy as np

from src.data.cleaning import clean_fact_sales


def test_deduplicates_exact_transaction_id(
    raw_fact_sales, dim_customer, dim_product, dim_store, dim_date
):
    cleaned, qa = clean_fact_sales(
        raw_fact_sales, dim_customer, dim_product, dim_store, dim_date
    )
    assert qa.duplicate_rows_removed == 1
    assert (cleaned["transaction_id"] == "T001").sum() == 1


def test_flags_bad_product_fk_but_keeps_row(
    raw_fact_sales, dim_customer, dim_product, dim_store, dim_date
):
    cleaned, qa = clean_fact_sales(
        raw_fact_sales, dim_customer, dim_product, dim_store, dim_date
    )
    row = cleaned[cleaned["transaction_id"] == "T004"].iloc[0]
    assert not row["is_valid"]
    assert "bad_product_fk" in row["invalid_reasons"]
    assert qa.invalid_bad_product_fk == 1


def test_flags_bad_store_fk_but_keeps_row(
    raw_fact_sales, dim_customer, dim_product, dim_store, dim_date
):
    cleaned, qa = clean_fact_sales(
        raw_fact_sales, dim_customer, dim_product, dim_store, dim_date
    )
    row = cleaned[cleaned["transaction_id"] == "T005"].iloc[0]
    assert not row["is_valid"]
    assert "bad_store_fk" in row["invalid_reasons"]


def test_zero_quantity_is_invalid(
    raw_fact_sales, dim_customer, dim_product, dim_store, dim_date
):
    cleaned, qa = clean_fact_sales(
        raw_fact_sales, dim_customer, dim_product, dim_store, dim_date
    )
    row = cleaned[cleaned["transaction_id"] == "T006"].iloc[0]
    assert not row["is_valid"]
    assert "zero_quantity" in row["invalid_reasons"]


def test_negative_quantity_is_a_return_not_invalid(
    raw_fact_sales, dim_customer, dim_product, dim_store, dim_date
):
    """Regression test for the exact bug we found and fixed in Step 4:
    negative quantity (a return) must stay is_valid=True, not get caught
    by the same check that flags zero-quantity rows as invalid.
    """
    cleaned, qa = clean_fact_sales(
        raw_fact_sales, dim_customer, dim_product, dim_store, dim_date
    )
    row = cleaned[cleaned["transaction_id"] == "T007"].iloc[0]
    assert row["is_return"]
    assert row["is_valid"]
    assert row["invalid_reasons"] == ""


def test_nonpositive_price_is_invalid(
    raw_fact_sales, dim_customer, dim_product, dim_store, dim_date
):
    cleaned, qa = clean_fact_sales(
        raw_fact_sales, dim_customer, dim_product, dim_store, dim_date
    )
    row = cleaned[cleaned["transaction_id"] == "T008"].iloc[0]
    assert not row["is_valid"]
    assert "nonpositive_price" in row["invalid_reasons"]


def test_date_outside_calendar_is_invalid(
    raw_fact_sales, dim_customer, dim_product, dim_store, dim_date
):
    cleaned, qa = clean_fact_sales(
        raw_fact_sales, dim_customer, dim_product, dim_store, dim_date
    )
    row = cleaned[cleaned["transaction_id"] == "T009"].iloc[0]
    assert not row["is_valid"]
    assert "date_outside_calendar" in row["invalid_reasons"]


def test_recomputes_canonical_financial_fields(
    raw_fact_sales, dim_customer, dim_product, dim_store, dim_date
):
    """T010's source gross_sales (999.0) is deliberately wrong.
    quantity=2 * unit_price=40.0 = 80.0 is the canonical value we expect."""
    cleaned, qa = clean_fact_sales(
        raw_fact_sales, dim_customer, dim_product, dim_store, dim_date
    )
    row = cleaned[cleaned["transaction_id"] == "T010"].iloc[0]
    assert row["gross_sales"] == 80.0
    assert row["qa_mismatch"]
    assert qa.financial_field_mismatches["gross_sales"] == 1


def test_orphan_customer_flagged_but_row_stays_valid(
    raw_fact_sales, dim_customer, dim_product, dim_store, dim_date
):
    """Regression test for the Step 5 fix: a bad customer_id should NOT
    make the row is_valid=False (it doesn't break revenue/margin math),
    only has_valid_customer=False."""
    cleaned, qa = clean_fact_sales(
        raw_fact_sales, dim_customer, dim_product, dim_store, dim_date
    )
    row = cleaned[cleaned["transaction_id"] == "T011"].iloc[0]
    assert not row["has_valid_customer"]
    assert row["is_valid"]
    assert qa.orphan_customer_id == 1


def test_category_replaced_with_clean_dim_product_join(
    raw_fact_sales, dim_customer, dim_product, dim_store, dim_date
):
    cleaned, qa = clean_fact_sales(
        raw_fact_sales, dim_customer, dim_product, dim_store, dim_date
    )
    clean_row = cleaned[cleaned["transaction_id"] == "T001"].iloc[0]
    assert clean_row["category"] == "Electronics"


def test_no_rows_are_dropped_only_flagged(
    raw_fact_sales, dim_customer, dim_product, dim_store, dim_date
):
    cleaned, qa = clean_fact_sales(
        raw_fact_sales, dim_customer, dim_product, dim_store, dim_date
    )
    # 11 raw rows, 1 exact duplicate removed -> 10 remain, ALL kept (flagged, not dropped)
    assert qa.total_rows_raw == 11
    assert len(cleaned) == 10
