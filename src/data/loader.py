"""Load raw dimension and fact tables from the /data/raw directory."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"


def load_dim_customer(data_dir: Path = DEFAULT_DATA_DIR) -> pd.DataFrame:
    """Load the customer dimension table."""
    return pd.read_csv(data_dir / "dim_customer.csv", dtype={"customer_id": "string"})


def load_dim_date(data_dir: Path = DEFAULT_DATA_DIR) -> pd.DataFrame:
    """Load the date dimension table, with `date` parsed as a real datetime."""
    df = pd.read_csv(data_dir / "dim_date.csv")
    df["date"] = pd.to_datetime(df["date"])
    return df


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
    df["transaction_date"] = pd.to_datetime(df["transaction_date"], errors="coerce")
    return df


def load_all(data_dir: Path = DEFAULT_DATA_DIR) -> dict[str, pd.DataFrame]:
    """Load all five raw tables into a dict keyed by table name."""
    return {
        "customer": load_dim_customer(data_dir),
        "date": load_dim_date(data_dir),
        "product": load_dim_product(data_dir),
        "store": load_dim_store(data_dir),
        "sales": load_fact_sales(data_dir),
    }
