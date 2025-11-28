"""Tests for the Extract step."""

import csv
import tempfile
from pathlib import Path

import pytest

from etl.extract import extract_all_files, _infer_data_type, _infer_period


class TestInferDataType:
    def test_sales_csv(self):
        assert _infer_data_type("sales_2024-01.csv") == "sales"

    def test_bookings_csv(self):
        assert _infer_data_type("bookings_2024-03.csv") == "bookings"

    def test_booking_singular(self):
        assert _infer_data_type("booking_2024-06.xlsx") == "bookings"

    def test_unknown(self):
        assert _infer_data_type("report_2024-01.csv") is None


class TestInferPeriod:
    def test_standard(self):
        assert _infer_period("sales_2024-01.csv") == "2024-01"

    def test_bookings(self):
        assert _infer_period("bookings_2024-12.xlsx") == "2024-12"

    def test_no_period(self):
        assert _infer_period("sales.csv") == "unknown"


class TestExtractAllFiles:
    def test_extracts_from_known_branch(self, tmp_path):
        """Create a minimal branch_hanoi folder with a sales CSV and verify extraction."""
        branch_dir = tmp_path / "branch_hanoi"
        branch_dir.mkdir()

        csv_path = branch_dir / "sales_2024-01.csv"
        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["transaction_id", "date", "service_name", "total_amount"])
            writer.writerow(["TXN-001", "2024-01-15", "Beer", "35000"])

        results = extract_all_files(data_dir=tmp_path, force=True)
        assert len(results) == 1
        assert results[0].branch_name == "Ha Noi - Hoan Kiem"
        assert results[0].data_type == "sales"
        assert len(results[0].dataframe) == 1

    def test_skips_unknown_branch(self, tmp_path):
        """Unknown branch folders should be skipped with a warning."""
        unknown = tmp_path / "branch_unknown"
        unknown.mkdir()
        (unknown / "sales_2024-01.csv").write_text("a,b\n1,2\n")

        results = extract_all_files(data_dir=tmp_path, force=True)
        assert len(results) == 0

    def test_empty_directory(self, tmp_path):
        results = extract_all_files(data_dir=tmp_path, force=True)
        assert results == []

    def test_branch_filter(self, tmp_path):
        """With branch_filter, only matching branches should be processed."""
        for folder in ["branch_hanoi", "branch_hcm"]:
            d = tmp_path / folder
            d.mkdir()
            with open(d / "sales_2024-01.csv", "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["transaction_id", "date", "service_name", "total_amount"])
                w.writerow(["TXN-001", "2024-01-15", "Beer", "35000"])

        results = extract_all_files(data_dir=tmp_path, force=True, branch_filter="branch_hcm")
        assert len(results) == 1
        assert results[0].branch_name == "TP.HCM - Quan 1"
