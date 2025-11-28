"""Tests for the Load step.

Note: These tests verify the dry-run path (no database required).
Full integration tests with a live PostgreSQL instance should be
run separately with: python run_pipeline.py
"""

import pandas as pd
import pytest
from pathlib import Path

from etl.extract import ExtractedFile
from etl.transform import transform_to_star_schema, StarSchemaData
from etl.load import load_to_database


def _make_files():
    """Create minimal test files for the full pipeline."""
    sales_df = pd.DataFrame({
        "transaction_id": ["TXN-001"],
        "date": pd.to_datetime(["2024-01-15"]),
        "service_name": ["Beer"],
        "category": ["Food & Beverage"],
        "quantity": [2],
        "unit_price": [35000],
        "discount_amount": [0],
        "total_amount": [70000],
        "payment_method": ["Cash"],
    })
    booking_df = pd.DataFrame({
        "booking_id": ["BK-001"],
        "date": pd.to_datetime(["2024-01-15"]),
        "room_id": ["HN-S01"],
        "room_name": ["Lotus Small 1"],
        "room_type": ["Small"],
        "customer_name": ["Nguyen An"],
        "start_hour": [18],
        "end_hour": [21],
        "duration_hours": [3],
        "num_guests": [4],
        "room_fee": [360000],
        "extra_charges": [0],
        "total_charge": [360000],
    })
    return [
        ExtractedFile(Path("fake/sales.csv"), "branch_hanoi", "Ha Noi - Hoan Kiem", "sales", "2024-01", sales_df),
        ExtractedFile(Path("fake/bookings.csv"), "branch_hanoi", "Ha Noi - Hoan Kiem", "bookings", "2024-01", booking_df),
    ]


class TestLoadDryRun:
    def test_dry_run_returns_counts(self):
        files = _make_files()
        schema = transform_to_star_schema(files)
        counts = load_to_database(schema, files=files, dry_run=True)

        assert isinstance(counts, dict)
        assert "dim_branch" in counts
        assert "fact_sales" in counts
        assert "fact_bookings" in counts

    def test_dry_run_nonzero_dimensions(self):
        files = _make_files()
        schema = transform_to_star_schema(files)
        counts = load_to_database(schema, files=files, dry_run=True)

        assert counts["dim_branch"] >= 1
        assert counts["dim_time"] >= 1

    def test_dry_run_nonzero_facts(self):
        files = _make_files()
        schema = transform_to_star_schema(files)
        counts = load_to_database(schema, files=files, dry_run=True)

        assert counts["fact_sales"] >= 1
        assert counts["fact_bookings"] >= 1
