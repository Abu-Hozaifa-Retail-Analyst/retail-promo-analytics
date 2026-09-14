"""Build the unified analysis table: valid, non-return sales joined to dims."""

from __future__ import annotations

import pandas as pd

_PROMO_DEPTH_BINS = [-0.001, 0.0, 0.05, 0.15, 0.30, 1.0]
_PROMO_DEPTH_LABELS = ["No Promo", "0-5%", "5-15%", "15-30%", "30%+"]


def build_sales_analysis_table(
    sales_clean: pd.DataFrame,
    customer: pd.DataFrame,
    store: pd.DataFrame,
    date: pd.DataFrame,
    *,
    include_returns: bool = False,
    valid_only: bool = True,
) -> pd.DataFrame:
    """Join cleaned fact_sales to all dimensions and derive promo fields."""
    df = sales_clean
    if valid_only:
        df = df[df["is_valid"]]
    if not include_returns:
        df = df[~df["is_return"]]
    df = df.copy()

    df["discount_pct"] = (
        df["discount_amount"] / df["gross_sales"].replace(0, pd.NA)
    ).astype("float64")
    df["discount_pct"] = df["discount_pct"].fillna(0.0).clip(lower=0.0)
    df["is_promo"] = df["discount_amount"] > 0
    df["promo_depth_bucket"] = pd.cut(
        df["discount_pct"], bins=_PROMO_DEPTH_BINS, labels=_PROMO_DEPTH_LABELS
    )

    df = df.merge(
        store[["store_id", "store_name", "region", "store_type"]],
        on="store_id",
        how="left",
    )
    df = df.merge(
        customer[["customer_id", "customer_segment", "gender", "age", "city"]].rename(
            columns={"city": "customer_city"}
        ),
        on="customer_id",
        how="left",
    )
    df = df.merge(
        date[
            [
                "date_key",
                "date",
                "year",
                "quarter",
                "month",
                "month_name",
                "week",
                "day_name",
            ]
        ],
        left_on=df["transaction_date"].dt.strftime("%Y%m%d").astype("int64"),
        right_on="date_key",
        how="left",
    )
    df = df.drop(columns=["date_key", "key_0"], errors="ignore")

    return df.reset_index(drop=True)
