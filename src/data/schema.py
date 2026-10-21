"""Check that the five input tables have the columns and value types the pipeline relies on.

Without this check a renamed or missing column surfaces as a bare ``KeyError`` deep inside
the analysis. Here every problem across all five tables is collected first and reported
together, in business terms, so the data owner can fix the source files in one pass.

Only *structure* is checked: row-level data problems (unknown product IDs, zero quantities,
...) are not errors. ``src.data.cleaning`` flags those rows and keeps them.
"""

from __future__ import annotations

import difflib
import warnings
from dataclasses import dataclass

import pandas as pd

MAX_EXAMPLES = 3


class SchemaError(ValueError):
    """The input data does not have the structure the pipeline needs."""


@dataclass(frozen=True)
class TableSpec:
    """What one input table must look like."""

    file: str
    required: tuple[str, ...]
    numeric: tuple[str, ...] = ()
    dates: tuple[str, ...] = ()
    strict_dates: bool = True  # True: every value must parse. False: fail only if none parse.
    unique_key: str | None = None


SPECS: dict[str, TableSpec] = {
    "sales": TableSpec(
        file="fact_sales.csv",
        required=(
            "transaction_id",
            "transaction_date",
            "customer_id",
            "product_id",
            "store_id",
            "quantity",
            "unit_price",
            "discount_amount",
            "gross_sales",
            "net_sales",
            "unit_cost",
            "cost_amount",
            "profit_amount",
            "gross_margin_pct",
        ),
        numeric=(
            "quantity",
            "unit_price",
            "discount_amount",
            "gross_sales",
            "net_sales",
            "unit_cost",
            "cost_amount",
            "profit_amount",
            "gross_margin_pct",
        ),
        dates=("transaction_date",),
        strict_dates=False,  # unreadable dates are flagged per row by the cleaning step
    ),
    "customer": TableSpec(
        file="dim_customer.csv",
        required=("customer_id", "customer_segment", "gender", "age", "city"),
        numeric=("age",),
        unique_key="customer_id",
    ),
    "date": TableSpec(
        file="dim_date.csv",
        required=("date_key", "date", "year", "quarter", "month", "month_name", "week", "day_name"),
        numeric=("date_key", "year", "quarter", "month", "week"),
        dates=("date",),
        unique_key="date_key",
    ),
    "product": TableSpec(
        file="dim_product.csv",
        required=("product_id", "category", "unit_cost", "selling_price"),
        numeric=("unit_cost", "selling_price"),
        unique_key="product_id",
    ),
    "store": TableSpec(
        file="dim_store.csv",
        required=("store_id", "store_name", "region", "store_type"),
        unique_key="store_id",
    ),
}


def _normalize(name: str) -> str:
    """Lower-case and drop separators, so 'UnitPrice' and 'unit_price' compare equal."""
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


def _examples(values: pd.Series) -> str:
    shown = ", ".join(repr(v) for v in values.drop_duplicates().head(MAX_EXAMPLES))
    return f"e.g. {shown}"


def _missing_column_message(column: str, present: list[str], required: tuple[str, ...]) -> str:
    """Name the missing column and, when the file has a look-alike, say which one."""
    spare = [c for c in present if c not in required]  # a column that is already used cannot be the renamed one
    same_letters = [c for c in spare if _normalize(c) == _normalize(column)]
    if same_letters:
        return f"missing column '{column}' (found '{same_letters[0]}': rename it to '{column}')"
    close = difflib.get_close_matches(column, spare, n=1, cutoff=0.7)
    if close:
        return f"missing column '{column}' (did you mean '{close[0]}'?)"
    return f"missing column '{column}'"


def _check_table(df: pd.DataFrame, spec: TableSpec) -> list[str]:
    """Return the problems found in one table (an empty list means it is fine)."""
    if len(df) == 0:
        return ["the table has no rows"]

    problems: list[str] = []
    present = list(df.columns)
    for column in spec.required:
        if column not in df.columns:
            problems.append(_missing_column_message(column, present, spec.required))

    for column in spec.numeric:
        if column not in df.columns:
            continue
        values = df[column]
        converted = pd.to_numeric(values, errors="coerce")
        bad = values[converted.isna() & values.notna()]
        if len(bad):
            problems.append(
                f"column '{column}' must be numeric but has {len(bad):,} non-numeric value(s) ({_examples(bad)})"
            )
        elif converted.isna().all():
            problems.append(f"column '{column}' is completely empty")

    for column in spec.dates:
        if column not in df.columns:
            continue
        values = df[column]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # mixed formats make pandas warn; the unreadable ones are reported below
            parsed = pd.to_datetime(values, errors="coerce")
        bad = values[parsed.isna() & values.notna()]
        if spec.strict_dates and len(bad):
            problems.append(
                f"column '{column}' must hold dates but has {len(bad):,} unreadable value(s) ({_examples(bad)})"
            )
        elif not spec.strict_dates and parsed.isna().all():
            problems.append(f"column '{column}' has no readable dates")

    key = spec.unique_key
    if key and key in df.columns:
        empty = int(df[key].isna().sum())
        if empty:
            problems.append(f"key column '{key}' has {empty:,} empty value(s)")
        repeats = df[key].dropna()
        repeats = repeats[repeats.duplicated(keep=False)]
        if len(repeats):
            problems.append(
                f"key column '{key}' must be unique but {repeats.nunique():,} value(s) repeat ({_examples(repeats)})"
            )
    return problems


def find_problems(tables: dict[str, pd.DataFrame]) -> dict[str, list[str]]:
    """Check every table in ``SPECS`` and return ``{file name: [problems]}`` (only files with problems)."""
    found: dict[str, list[str]] = {}
    for name, spec in SPECS.items():
        problems = _check_table(tables[name], spec)
        if problems:
            found[spec.file] = problems
    return found


def validate_tables(tables: dict[str, pd.DataFrame]) -> None:
    """Raise one ``SchemaError`` listing every problem, or return quietly when the data is usable."""
    found = find_problems(tables)
    if not found:
        return
    total = sum(len(p) for p in found.values())
    lines = [f"The input data does not match the expected schema ({total} problem(s)):"]
    for file, problems in found.items():
        lines.append(f"  {file}")
        lines.extend(f"    - {p}" for p in problems)
    lines.append("Fix the source files (see 'Data expectations' in the README) and run again.")
    raise SchemaError("\n".join(lines))
