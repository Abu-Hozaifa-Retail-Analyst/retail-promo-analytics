"""Load raw dimension and fact tables from the /data/raw directory.

The individual ``load_*`` functions are tolerant: a missing column is not an error here,
because ``load_all`` checks the structure of every table afterwards (``src.data.schema``)
and reports all problems together.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.data.schema import SPECS, SchemaError, validate_tables

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"


def _parse_dates(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """Turn a date column into datetimes when it exists; unreadable values become NaT."""
    if column in df.columns:
        df[column] = pd.to_datetime(df[column], errors="coerce")
    return df


def load_dim_customer(data_dir: Path = DEFAULT_DATA_DIR) -> pd.DataFrame:
    """Load the customer dimension table."""
    return pd.read_csv(data_dir / "dim_customer.csv", dtype={"customer_id": "string"})


def load_dim_date(data_dir: Path = DEFAULT_DATA_DIR) -> pd.DataFrame:
    """Load the date dimension table, with `date` parsed as a real datetime."""
    return _parse_dates(pd.read_csv(data_dir / "dim_date.csv"), "date")


def load_dim_product(data_dir: Path = DEFAULT_DATA_DIR) -> pd.DataFrame:
    """Load the product dimension table."""
    return pd.read_csv(data_dir / "dim_product.csv", dtype={"product_id": "string"})


def load_dim_store(data_dir: Path = DEFAULT_DATA_DIR) -> pd.DataFrame:
    """Load the store dimension table."""
    return pd.read_csv(data_dir / "dim_store.csv", dtype={"store_id": "string"})


def load_fact_sales(data_dir: Path = DEFAULT_DATA_DIR) -> pd.DataFrame:
    """Load the raw sales fact table. No cleaning is applied here."""
    df = pd.read_csv(
        data_dir / "fact_sales.csv",
        dtype={"customer_id": "string", "product_id": "string", "store_id": "string"},
    )
    return _parse_dates(df, "transaction_date")


def load_all(data_dir: Path = DEFAULT_DATA_DIR, *, validate: bool = True) -> dict[str, pd.DataFrame]:
    """Load all five raw tables into a dict keyed by table name.

    Args:
        data_dir: Directory holding the five CSVs.
        validate: Check files and columns before returning (see ``src.data.schema``).

    Raises:
        SchemaError: A file is missing, or a table lacks a required column or has unusable values.
    """
    data_dir = Path(data_dir)
    if validate:
        missing = [spec.file for spec in SPECS.values() if not (data_dir / spec.file).exists()]
        if missing:
            listing = "\n".join(f"    - {name}" for name in missing)
            raise SchemaError(
                f"Input files not found in {data_dir}:\n{listing}\n"
                "Put all five CSVs there (see 'Data expectations' in the README)."
            )
    tables = {
        "customer": load_dim_customer(data_dir),
        "date": load_dim_date(data_dir),
        "product": load_dim_product(data_dir),
        "store": load_dim_store(data_dir),
        "sales": load_fact_sales(data_dir),
    }
    if validate:
        validate_tables(tables)
    return tables
