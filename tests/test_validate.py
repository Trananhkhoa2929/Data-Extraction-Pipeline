"""Tests for the Validate & Clean step."""

import pandas as pd
import pytest

from etl.extract import ExtractedFile
from etl.validate import validate_and_clean, _parse_dates


class TestParseDates:
    def test_iso_format(self):
        s = pd.Series(["2024-01-15", "2024-06-30"])
        result = _parse_dates(s)
        assert result.iloc[0] == pd.Timestamp("2024-01-15")

    def test_dd_mm_yyyy(self):
        s = pd.Series(["15/01/2024", "30/06/2024"])
        result = _parse_dates(s)
        assert result.iloc[0] == pd.Timestamp("2024-01-15")


class TestValidateSales:
    def _make_sales_file(self, df: pd.DataFrame) -> ExtractedFile:
        from pathlib import Path
        return ExtractedFile(
            filepath=Path("fake/sales_2024-01.csv"),
            branch_folder="branch_hanoi",
            branch_name="Ha Noi - Hoan Kiem",
            data_type="sales",
            period="2024-01",
            dataframe=df,
        )

    def test_drops_null_critical_fields(self):
        df = pd.DataFrame({
            "transaction_id": ["TXN-001", None],
            "date": ["2024-01-15", "2024-01-16"],
            "service_name": ["Beer", "Cocktail"],
            "total_amount": [35000, 65000],
        })
        ef = self._make_sales_file(df)
        result = validate_and_clean([ef])
        assert len(result) == 1
        assert len(result[0].dataframe) == 1

    def test_normalizes_text(self):
        df = pd.DataFrame({
            "transaction_id": ["TXN-001"],
            "date": ["2024-01-15"],
            "service_name": ["  beer  "],
            "category": [" food & beverage "],
            "total_amount": [35000],
        })
        ef = self._make_sales_file(df)
        result = validate_and_clean([ef])
        assert result[0].dataframe.iloc[0]["service_name"] == "Beer"
        assert result[0].dataframe.iloc[0]["category"] == "Food & Beverage"

    def test_deduplicates_transactions(self):
        df = pd.DataFrame({
            "transaction_id": ["TXN-001", "TXN-001"],
            "date": ["2024-01-15", "2024-01-15"],
            "service_name": ["Beer", "Beer"],
            "total_amount": [35000, 35000],
        })
        ef = self._make_sales_file(df)
        result = validate_and_clean([ef])
        assert len(result[0].dataframe) == 1

    def test_fills_default_payment_method(self):
        df = pd.DataFrame({
            "transaction_id": ["TXN-001"],
            "date": ["2024-01-15"],
            "service_name": ["Beer"],
            "total_amount": [35000],
        })
        ef = self._make_sales_file(df)
        result = validate_and_clean([ef])
        assert result[0].dataframe.iloc[0]["payment_method"] == "Cash"


class TestValidateBookings:
    def _make_booking_file(self, df: pd.DataFrame) -> ExtractedFile:
        from pathlib import Path
        return ExtractedFile(
            filepath=Path("fake/bookings_2024-01.csv"),
            branch_folder="branch_hanoi",
            branch_name="Ha Noi - Hoan Kiem",
            data_type="bookings",
            period="2024-01",
            dataframe=df,
        )

    def test_computes_duration(self):
        df = pd.DataFrame({
            "booking_id": ["BK-001"],
            "date": ["2024-01-15"],
            "room_id": ["HN-S01"],
            "start_hour": [18],
            "end_hour": [21],
            "total_charge": [360000],
        })
        ef = self._make_booking_file(df)
        result = validate_and_clean([ef])
        assert result[0].dataframe.iloc[0]["duration_hours"] == 3

    def test_fills_customer_name(self):
        df = pd.DataFrame({
            "booking_id": ["BK-001"],
            "date": ["2024-01-15"],
            "room_id": ["HN-S01"],
            "total_charge": [360000],
        })
        ef = self._make_booking_file(df)
        result = validate_and_clean([ef])
        assert result[0].dataframe.iloc[0]["customer_name"] == "Walk-in"
