"""Data-quality handling for fact_sales."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

_MISMATCH_TOLERANCE = 0.01


@dataclass
class QASummary:
    """Structured data-quality report produced while cleaning fact_sales."""

    total_rows_raw: int = 0
    duplicate_rows_removed: int = 0
    total_rows_after_dedup: int = 0
    invalid_bad_product_fk: int = 0
    invalid_bad_store_fk: int = 0
    invalid_missing_date: int = 0
    invalid_date_outside_calendar: int = 0
    invalid_zero_quantity: int = 0
    invalid_nonpositive_price: int = 0
    missing_customer_id: int = 0
    total_invalid_rows: int = 0
    total_valid_rows: int = 0
    return_rows: int = 0
    financial_field_mismatches: dict[str, int] = field(default_factory=dict)


def clean_fact_sales(
    sales: pd.DataFrame,
    product: pd.DataFrame,
    store: pd.DataFrame,
    date: pd.DataFrame,
) -> tuple[pd.DataFrame, QASummary]:
    """Deduplicate, validate, and recompute canonical fields for fact_sales."""
    qa = QASummary()
    qa.total_rows_raw = len(sales)

    df = sales.copy()

    # --- 1. Deduplicate exact transaction_id repeats (keep first) -----
    dupe_mask = df["transaction_id"].duplicated(keep="first")
    qa.duplicate_rows_removed = int(dupe_mask.sum())
    df = df.loc[~dupe_mask].reset_index(drop=True)
    qa.total_rows_after_dedup = len(df)

    # --- 2. Validity flags (rows are KEPT, only flagged) --------------
    valid_product_ids = set(product["product_id"])
    valid_store_ids = set(store["store_id"])
    min_date, max_date = date["date"].min(), date["date"].max()

    bad_product = ~df["product_id"].isin(valid_product_ids)
    bad_store = ~df["store_id"].isin(valid_store_ids)
    missing_date = df["transaction_date"].isna()
    outside_calendar = (~missing_date) & (
        (df["transaction_date"] < min_date) | (df["transaction_date"] > max_date)
    )
    # Only quantity == 0 is invalid. Negative quantity is a RETURN,
    # not a data-quality problem — handled separately below.
    bad_quantity = df["quantity"] == 0
    bad_price = df["unit_price"] <= 0

    qa.invalid_bad_product_fk = int(bad_product.sum())
    qa.invalid_bad_store_fk = int(bad_store.sum())
    qa.invalid_missing_date = int(missing_date.sum())
    qa.invalid_date_outside_calendar = int(outside_calendar.sum())
    qa.invalid_zero_quantity = int(bad_quantity.sum())
    qa.invalid_nonpositive_price = int(bad_price.sum())
    qa.missing_customer_id = int(df["customer_id"].isna().sum())

    core_invalid = (
        bad_product
        | bad_store
        | missing_date
        | outside_calendar
        | bad_quantity
        | bad_price
    )
    df["is_valid"] = ~core_invalid

    reason_flags = {
        "bad_product_fk": bad_product,
        "bad_store_fk": bad_store,
        "missing_date": missing_date,
        "date_outside_calendar": outside_calendar,
        "zero_quantity": bad_quantity,
        "nonpositive_price": bad_price,
    }
    reason_df = pd.DataFrame(reason_flags)
    df["invalid_reasons"] = reason_df.apply(
        lambda row: "|".join([name for name, flag in row.items() if flag]),
        axis=1,
    )

    qa.total_invalid_rows = int((~df["is_valid"]).sum())
    qa.total_valid_rows = int(df["is_valid"].sum())

    df["is_return"] = df["quantity"] < 0
    qa.return_rows = int(df["is_return"].sum())

    # --- 3. Recompute canonical financial fields -----------------------
    calc_gross = df["quantity"] * df["unit_price"]
    calc_net = calc_gross - df["discount_amount"]
    calc_cost = df["quantity"] * df["unit_cost"]
    calc_profit = calc_net - calc_cost
    calc_margin = np.where(calc_net != 0, (calc_profit / calc_net) * 100, np.nan)

    for name, provided_col, recomputed in [
        ("gross_sales", "gross_sales", calc_gross),
        ("net_sales", "net_sales", calc_net),
        ("cost_amount", "cost_amount", calc_cost),
        ("profit_amount", "profit_amount", calc_profit),
        ("gross_margin_pct", "gross_margin_pct", calc_margin),
    ]:
        mismatch = (df[provided_col] - recomputed).abs() > _MISMATCH_TOLERANCE
        mismatch = mismatch.fillna(False)
        qa.financial_field_mismatches[name] = int(mismatch.sum())
        df[f"_mismatch_{name}"] = mismatch

    mismatch_cols = [c for c in df.columns if c.startswith("_mismatch_")]
    df["qa_mismatch"] = df[mismatch_cols].any(axis=1)
    df = df.drop(columns=mismatch_cols)

    df["gross_sales"] = calc_gross
    df["net_sales"] = calc_net
    df["cost_amount"] = calc_cost
    df["profit_amount"] = calc_profit
    df["gross_margin_pct"] = calc_margin

    # --- 4. Replace noisy category column with clean dim_product join --
    df = df.drop(columns=["category"])
    df = df.merge(product[["product_id", "category"]], on="product_id", how="left")

    return df, qa


def qa_summary_to_markdown(qa: QASummary) -> str:
    """Render a QASummary as a short Markdown table."""
    lines = [
        "| Metric | Value |",
        "|---|---|",
        f"| Raw rows | {qa.total_rows_raw:,} |",
        f"| Duplicate rows removed | {qa.duplicate_rows_removed:,} |",
        f"| Rows after dedup | {qa.total_rows_after_dedup:,} |",
        f"| Invalid: bad product FK | {qa.invalid_bad_product_fk:,} |",
        f"| Invalid: bad store FK | {qa.invalid_bad_store_fk:,} |",
        f"| Invalid: missing date | {qa.invalid_missing_date:,} |",
        f"| Invalid: date outside calendar | {qa.invalid_date_outside_calendar:,} |",
        f"| Invalid: zero quantity | {qa.invalid_zero_quantity:,} |",
        f"| Invalid: non-positive price | {qa.invalid_nonpositive_price:,} |",
        f"| **Total invalid rows (excluded from aggregates)** | **{qa.total_invalid_rows:,}** |",
        f"| **Total valid rows** | **{qa.total_valid_rows:,}** |",
        f"| Return rows (kept, analyzed separately) | {qa.return_rows:,} |",
        f"| Missing customer_id | {qa.missing_customer_id:,} |",
    ]
    for name, count in qa.financial_field_mismatches.items():
        lines.append(f"| QA mismatch: {name} (source vs recomputed) | {count:,} |")
    return "\n".join(lines)
