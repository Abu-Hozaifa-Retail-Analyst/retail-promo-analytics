"""Shared pytest fixtures: small, deterministic hand-built tables."""

from __future__ import annotations

import pandas as pd
import pytest


@pytest.fixture
def dim_product() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "product_id": ["P001", "P002"],
            "product_name": ["Widget", "Gadget"],
            "category": ["Electronics", "Home & Living"],
            "subcategory": ["Gizmos", "Furniture"],
            "brand": ["Acme", "Acme"],
            "unit_cost": [50.0, 20.0],
            "selling_price": [100.0, 40.0],
        }
    )


@pytest.fixture
def dim_store() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "store_id": ["S01", "S02"],
            "store_name": ["Store One", "Store Two"],
            "city": ["Riyadh", "Jeddah"],
            "region": ["Central", "Western"],
            "store_type": ["Mall", "Hypermarket"],
        }
    )


@pytest.fixture
def dim_customer() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "customer_id": ["C001", "C002"],
            "customer_name": ["Alice", "Bob"],
            "gender": ["Female", "Male"],
            "age": [30, 40],
            "city": ["Riyadh", "Jeddah"],
            "customer_segment": ["Premium", "Standard"],
        }
    )


@pytest.fixture
def dim_date() -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    return pd.DataFrame(
        {
            "date_key": [int(d.strftime("%Y%m%d")) for d in dates],
            "date": dates,
            "year": dates.year,
            "quarter": dates.quarter,
            "month": dates.month,
            "month_name": dates.strftime("%B"),
            "week": dates.isocalendar().week.values,
            "day": dates.day,
            "day_of_week": dates.dayofweek,
            "day_name": dates.strftime("%A"),
        }
    )


@pytest.fixture
def raw_fact_sales() -> pd.DataFrame:
    """One row per data-quality rule we handle, so each test traces to a specific row."""
    rows = [
        # T001: clean, no discount
        dict(
            transaction_id="T001",
            transaction_date="2024-01-01",
            customer_id="C001",
            product_id="P001",
            store_id="S01",
            quantity=2,
            unit_price=100.0,
            discount_amount=0.0,
            gross_sales=200.0,
            net_sales=200.0,
            unit_cost=50.0,
            cost_amount=100.0,
            profit_amount=100.0,
            gross_margin_pct=50.0,
            payment_method="Card",
            sales_channel="Store",
            category="Electronics",
        ),
        # T002: exact duplicate of T001 -> should be deduped away
        dict(
            transaction_id="T001",
            transaction_date="2024-01-01",
            customer_id="C001",
            product_id="P001",
            store_id="S01",
            quantity=2,
            unit_price=100.0,
            discount_amount=0.0,
            gross_sales=200.0,
            net_sales=200.0,
            unit_cost=50.0,
            cost_amount=100.0,
            profit_amount=100.0,
            gross_margin_pct=50.0,
            payment_method="Card",
            sales_channel="Store",
            category="Electronics",
        ),
        # T003: clean, WITH discount (a promo)
        dict(
            transaction_id="T003",
            transaction_date="2024-01-02",
            customer_id="C002",
            product_id="P001",
            store_id="S01",
            quantity=3,
            unit_price=100.0,
            discount_amount=30.0,
            gross_sales=300.0,
            net_sales=270.0,
            unit_cost=50.0,
            cost_amount=150.0,
            profit_amount=120.0,
            gross_margin_pct=44.44,
            payment_method="Cash",
            sales_channel="Store",
            category="Electronics",
        ),
        # T004: bad product FK
        dict(
            transaction_id="T004",
            transaction_date="2024-01-02",
            customer_id="C001",
            product_id="P999",
            store_id="S01",
            quantity=1,
            unit_price=10.0,
            discount_amount=0.0,
            gross_sales=10.0,
            net_sales=10.0,
            unit_cost=5.0,
            cost_amount=5.0,
            profit_amount=5.0,
            gross_margin_pct=50.0,
            payment_method="Card",
            sales_channel="Store",
            category="Unknown",
        ),
        # T005: bad store FK
        dict(
            transaction_id="T005",
            transaction_date="2024-01-02",
            customer_id="C001",
            product_id="P001",
            store_id="S99",
            quantity=1,
            unit_price=100.0,
            discount_amount=0.0,
            gross_sales=100.0,
            net_sales=100.0,
            unit_cost=50.0,
            cost_amount=50.0,
            profit_amount=50.0,
            gross_margin_pct=50.0,
            payment_method="Card",
            sales_channel="Store",
            category="Electronics",
        ),
        # T006: zero quantity -> invalid
        dict(
            transaction_id="T006",
            transaction_date="2024-01-03",
            customer_id="C001",
            product_id="P001",
            store_id="S01",
            quantity=0,
            unit_price=100.0,
            discount_amount=0.0,
            gross_sales=0.0,
            net_sales=0.0,
            unit_cost=50.0,
            cost_amount=0.0,
            profit_amount=0.0,
            gross_margin_pct=0.0,
            payment_method="Card",
            sales_channel="Store",
            category="Electronics",
        ),
        # T007: negative quantity -> a RETURN, must stay valid, is_return=True
        dict(
            transaction_id="T007",
            transaction_date="2024-01-03",
            customer_id="C001",
            product_id="P001",
            store_id="S01",
            quantity=-1,
            unit_price=100.0,
            discount_amount=0.0,
            gross_sales=-100.0,
            net_sales=-100.0,
            unit_cost=50.0,
            cost_amount=-50.0,
            profit_amount=-50.0,
            gross_margin_pct=50.0,
            payment_method="Card",
            sales_channel="Store",
            category="Electronics",
        ),
        # T008: non-positive price -> invalid
        dict(
            transaction_id="T008",
            transaction_date="2024-01-03",
            customer_id="C001",
            product_id="P001",
            store_id="S01",
            quantity=1,
            unit_price=0.0,
            discount_amount=0.0,
            gross_sales=0.0,
            net_sales=0.0,
            unit_cost=50.0,
            cost_amount=50.0,
            profit_amount=-50.0,
            gross_margin_pct=0.0,
            payment_method="Card",
            sales_channel="Store",
            category="Electronics",
        ),
        # T009: date outside dim_date's calendar (which only covers Jan 1-10 2024)
        dict(
            transaction_id="T009",
            transaction_date="2024-05-01",
            customer_id="C001",
            product_id="P001",
            store_id="S01",
            quantity=1,
            unit_price=100.0,
            discount_amount=0.0,
            gross_sales=100.0,
            net_sales=100.0,
            unit_cost=50.0,
            cost_amount=50.0,
            profit_amount=50.0,
            gross_margin_pct=50.0,
            payment_method="Card",
            sales_channel="Store",
            category="Electronics",
        ),
        # T010: mismatched financial fields (gross_sales deliberately wrong)
        dict(
            transaction_id="T010",
            transaction_date="2024-01-04",
            customer_id="C002",
            product_id="P002",
            store_id="S02",
            quantity=2,
            unit_price=40.0,
            discount_amount=0.0,
            gross_sales=999.0,
            net_sales=999.0,
            unit_cost=20.0,
            cost_amount=40.0,
            profit_amount=40.0,
            gross_margin_pct=50.0,
            payment_method="Card",
            sales_channel="Online",
            category="Home & Living",
        ),
        # T011: orphan customer_id -> flags has_valid_customer=False, still is_valid
        dict(
            transaction_id="T011",
            transaction_date="2024-01-04",
            customer_id="C999",
            product_id="P001",
            store_id="S01",
            quantity=1,
            unit_price=100.0,
            discount_amount=0.0,
            gross_sales=100.0,
            net_sales=100.0,
            unit_cost=50.0,
            cost_amount=50.0,
            profit_amount=50.0,
            gross_margin_pct=50.0,
            payment_method="Card",
            sales_channel="Store",
            category="Electronics",
        ),
    ]
    df = pd.DataFrame(rows)
    df["transaction_date"] = pd.to_datetime(df["transaction_date"])
    return df
