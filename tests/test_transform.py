"""Tests for the Transform step."""

import pandas as pd
import pytest
from pathlib import Path

from etl.extract import ExtractedFile
from etl.transform import transform_to_star_schema


def _make_sales_file() -> ExtractedFile:
    df = pd.DataFrame({
        "transaction_id": ["TXN-001", "TXN-002", "TXN-003"],
        "date": pd.to_datetime(["2024-01-15", "2024-01-16", "2024-02-01"]),
        "service_name": ["Beer", "Cocktail", "Beer"],
        "category": ["Food & Beverage", "Food & Beverage", "Food & Beverage"],
        "quantity": [2, 1, 3],
        "unit_price": [35000, 65000, 35000],
        "discount_amount": [0, 0, 5000],
        "total_amount": [70000, 65000, 100000],
        "payment_method": ["Cash", "Card", "MoMo"],
    })
    return ExtractedFile(
        filepath=Path("fake/sales_2024-01.csv"),
        branch_folder="branch_hanoi",
        branch_name="Ha Noi - Hoan Kiem",
        data_type="sales",
        period="2024-01",
        dataframe=df,
    )


def _make_booking_file() -> ExtractedFile:
    df = pd.DataFrame({
        "booking_id": ["BK-001", "BK-002"],
        "date": pd.to_datetime(["2024-01-15", "2024-01-16"]),
        "room_id": ["HN-S01", "HN-M01"],
        "room_name": ["Lotus Small 1", "Orchid Medium 1"],
        "room_type": ["Small", "Medium"],
        "customer_name": ["Nguyen An", "Tran Binh"],
        "start_hour": [18, 20],
        "end_hour": [21, 23],
        "duration_hours": [3, 3],
        "num_guests": [4, 8],
        "room_fee": [360000, 600000],
        "extra_charges": [0, 50000],
        "total_charge": [360000, 650000],
    })
    return ExtractedFile(
        filepath=Path("fake/bookings_2024-01.csv"),
        branch_folder="branch_hanoi",
        branch_name="Ha Noi - Hoan Kiem",
        data_type="bookings",
        period="2024-01",
        dataframe=df,
    )


class TestTransform:
    def test_creates_all_tables(self):
        files = [_make_sales_file(), _make_booking_file()]
        result = transform_to_star_schema(files)

        assert not result.dim_branch.empty
        assert not result.dim_service.empty
        assert not result.dim_room.empty
        assert not result.dim_time.empty
        assert not result.fact_sales.empty
        assert not result.fact_bookings.empty

    def test_dim_branch_count(self):
        files = [_make_sales_file()]
        result = transform_to_star_schema(files)
        # Only one branch folder → one dim_branch row
        assert len(result.dim_branch) == 1
        assert result.dim_branch.iloc[0]["branch_name"] == "Ha Noi - Hoan Kiem"

    def test_dim_time_unique_dates(self):
        files = [_make_sales_file()]
        result = transform_to_star_schema(files)
        # 3 transactions on 3 dates (Jan 15, Jan 16, Feb 1) → 3 dim_time rows
        assert len(result.dim_time) == 3

    def test_dim_service_dedup(self):
        files = [_make_sales_file()]
        result = transform_to_star_schema(files)
        # "Beer" appears twice but should be deduplicated → 2 unique services
        assert len(result.dim_service) == 2

    def test_fact_sales_foreign_keys(self):
        files = [_make_sales_file(), _make_booking_file()]
        result = transform_to_star_schema(files)
        # All fact_sales rows should have valid FK values
        assert result.fact_sales["branch_key"].notna().all()
        assert result.fact_sales["service_key"].notna().all()
        assert result.fact_sales["time_key"].notna().all()

    def test_fact_bookings_foreign_keys(self):
        files = [_make_sales_file(), _make_booking_file()]
        result = transform_to_star_schema(files)
        assert result.fact_bookings["branch_key"].notna().all()
        assert result.fact_bookings["room_key"].notna().all()
        assert result.fact_bookings["time_key"].notna().all()
