"""Unit tests for src.data.schema and the validating loader."""

from __future__ import annotations

import pandas as pd
import pytest

from src.data.cleaning import clean_fact_sales
from src.data.loader import load_all
from src.data.schema import SchemaError, find_problems, validate_tables

FILES = {
    "customer": "dim_customer.csv",
    "date": "dim_date.csv",
    "product": "dim_product.csv",
    "store": "dim_store.csv",
    "sales": "fact_sales.csv",
}


@pytest.fixture
def tables(raw_fact_sales, dim_customer, dim_product, dim_store, dim_date):
    return {
        "sales": raw_fact_sales,
        "customer": dim_customer,
        "product": dim_product,
        "store": dim_store,
        "date": dim_date,
    }


def _write_csvs(tables, data_dir):
    for name, filename in FILES.items():
        tables[name].to_csv(data_dir / filename, index=False)


def test_valid_tables_have_no_problems(tables):
    assert find_problems(tables) == {}
    validate_tables(tables)  # does not raise


def test_missing_column_is_reported_under_its_file(tables):
    tables["sales"] = tables["sales"].drop(columns=["discount_amount"])
    problems = find_problems(tables)
    assert list(problems) == ["fact_sales.csv"]
    assert problems["fact_sales.csv"] == ["missing column 'discount_amount'"]


def test_renamed_column_gets_a_rename_hint(tables):
    tables["sales"] = tables["sales"].rename(columns={"unit_price": "UnitPrice", "discount_amount": "discount_amt"})
    messages = find_problems(tables)["fact_sales.csv"]
    assert "missing column 'unit_price' (found 'UnitPrice': rename it to 'unit_price')" in messages
    assert "missing column 'discount_amount' (did you mean 'discount_amt'?)" in messages


def test_non_numeric_values_are_reported_with_examples(tables):
    tables["sales"] = tables["sales"].astype({"quantity": "object"})
    tables["sales"].loc[0, "quantity"] = "two"
    message = find_problems(tables)["fact_sales.csv"][0]
    assert "column 'quantity' must be numeric" in message
    assert "1 non-numeric" in message
    assert "'two'" in message


def test_completely_empty_numeric_column_is_a_problem(tables):
    tables["sales"]["unit_cost"] = float("nan")
    assert "column 'unit_cost' is completely empty" in find_problems(tables)["fact_sales.csv"]


def test_dimension_keys_must_be_unique_and_filled(tables):
    tables["product"].loc[1, "product_id"] = "P001"  # duplicate of row 0
    tables["store"].loc[0, "store_id"] = None
    problems = find_problems(tables)
    assert any("'product_id' must be unique" in m for m in problems["dim_product.csv"])
    assert "key column 'store_id' has 1 empty value(s)" in problems["dim_store.csv"]


def test_unreadable_dates_a_few_ok_in_sales_but_all_bad_is_a_problem(tables):
    tables["sales"]["transaction_date"] = pd.to_datetime(tables["sales"]["transaction_date"])
    tables["sales"].loc[0, "transaction_date"] = pd.NaT  # cleaning flags these rows later
    assert find_problems(tables) == {}

    tables["sales"]["transaction_date"] = pd.NaT
    assert "column 'transaction_date' has no readable dates" in find_problems(tables)["fact_sales.csv"]

    tables["sales"]["transaction_date"] = pd.Timestamp("2024-01-02")
    tables["date"]["date"] = tables["date"]["date"].astype("object")
    tables["date"].loc[0, "date"] = "not a date"  # the calendar must be fully readable
    assert any("must hold dates" in m for m in find_problems(tables)["dim_date.csv"])


def test_empty_table_is_a_problem(tables):
    tables["store"] = tables["store"].iloc[0:0]
    assert find_problems(tables)["dim_store.csv"] == ["the table has no rows"]


def test_one_error_lists_every_problem_across_files(tables):
    tables["sales"] = tables["sales"].drop(columns=["quantity"])
    tables["product"] = tables["product"].drop(columns=["category"])
    with pytest.raises(SchemaError) as caught:
        validate_tables(tables)
    text = str(caught.value)
    assert "(2 problem(s))" in text
    assert "fact_sales.csv" in text and "dim_product.csv" in text
    assert "missing column 'quantity'" in text and "missing column 'category'" in text
    assert "Fix the source files" in text


def test_load_all_names_every_missing_file(tables, tmp_path):
    _write_csvs(tables, tmp_path)
    (tmp_path / "dim_store.csv").unlink()
    (tmp_path / "dim_date.csv").unlink()
    with pytest.raises(SchemaError) as caught:
        load_all(tmp_path)
    text = str(caught.value)
    assert "dim_store.csv" in text and "dim_date.csv" in text
    assert "fact_sales.csv" not in text


def test_load_all_accepts_a_valid_dataset(tables, tmp_path):
    _write_csvs(tables, tmp_path)
    loaded = load_all(tmp_path)
    assert set(loaded) == set(FILES)
    assert len(loaded["sales"]) == len(tables["sales"])


def test_load_all_reports_a_renamed_column_instead_of_a_key_error(tables, tmp_path):
    tables["sales"] = tables["sales"].rename(columns={"transaction_date": "TransactionDate"})
    _write_csvs(tables, tmp_path)
    with pytest.raises(SchemaError, match="found 'TransactionDate': rename it to 'transaction_date'"):
        load_all(tmp_path)
    assert "sales" in load_all(tmp_path, validate=False)  # the check can be switched off


def test_cleaning_works_without_a_category_column_in_the_fact_table(tables):
    sales = tables["sales"].drop(columns=["category"])
    cleaned, _ = clean_fact_sales(sales, tables["customer"], tables["product"], tables["store"], tables["date"])
    row = cleaned[cleaned["transaction_id"] == "T001"].iloc[0]
    assert row["category"] == "Electronics"  # taken from dim_product
