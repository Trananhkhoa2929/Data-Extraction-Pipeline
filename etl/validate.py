"""
Step 2: VALIDATE & CLEAN — Execute data quality checks on raw DataFrames.

Operations per data type:
  • Drop rows missing critical fields
  • Fill optional fields with defaults
  • Parse mixed-format dates → datetime
  • Normalize categorical text (strip + uppercase)
  • Deduplicate by transaction/booking ID
  • Log a validation report (rows dropped / fixed)
"""

from __future__ import annotations

import pandas as pd
import numpy as np

from etl.extract import ExtractedFile
from utils.logger import logger


# -- Date parsing -------------------------------------------------------------

_DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"]


def _parse_dates(series: pd.Series) -> pd.Series:
    """Try multiple date formats and return the first that works."""
    for fmt in _DATE_FORMATS:
        try:
            return pd.to_datetime(series, format=fmt)
        except (ValueError, TypeError):
            continue
    # Fallback: let pandas infer
    return pd.to_datetime(series, infer_datetime_format=True, errors="coerce")


# -- Sales validation ---------------------------------------------------------

_SALES_REQUIRED = ["transaction_id", "date", "service_name", "total_amount"]
_SALES_NUMERIC = ["quantity", "unit_price", "discount_amount", "total_amount"]
_SALES_CATEGORICAL = ["service_name", "category", "payment_method"]


def _validate_sales(df: pd.DataFrame, label: str) -> pd.DataFrame:
    """Validate and clean a sales DataFrame."""
    original_len = len(df)

    # Normalize column names
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")

    # Drop rows missing critical fields
    df = df.dropna(subset=[c for c in _SALES_REQUIRED if c in df.columns])

    # Parse dates
    if "date" in df.columns:
        df["date"] = _parse_dates(df["date"])
        df = df.dropna(subset=["date"])

    # Numeric coercion
    for col in _SALES_NUMERIC:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Fill optional columns
    if "quantity" in df.columns:
        df["quantity"] = df["quantity"].replace(0, 1).astype(int)
    if "discount_amount" not in df.columns:
        df["discount_amount"] = 0.0
    if "payment_method" not in df.columns:
        df["payment_method"] = "Cash"

    # Normalize categorical text
    for col in _SALES_CATEGORICAL:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().str.title()

    # Deduplicate
    if "transaction_id" in df.columns:
        df = df.drop_duplicates(subset=["transaction_id"], keep="first")

    dropped = original_len - len(df)
    if dropped:
        logger.warning("  %s: dropped %d invalid row(s).", label, dropped)

    return df.reset_index(drop=True)


# -- Bookings validation -----------------------------------------------------

_BOOKING_REQUIRED = ["booking_id", "date", "room_id", "total_charge"]
_BOOKING_NUMERIC = [
    "start_hour", "end_hour", "duration_hours",
    "num_guests", "room_fee", "extra_charges", "total_charge",
]


def _validate_bookings(df: pd.DataFrame, label: str) -> pd.DataFrame:
    """Validate and clean a bookings DataFrame."""
    original_len = len(df)

    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")

    df = df.dropna(subset=[c for c in _BOOKING_REQUIRED if c in df.columns])

    if "date" in df.columns:
        df["date"] = _parse_dates(df["date"])
        df = df.dropna(subset=["date"])

    for col in _BOOKING_NUMERIC:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    if "num_guests" in df.columns:
        df["num_guests"] = df["num_guests"].replace(0, 1).astype(int)

    if "customer_name" in df.columns:
        df["customer_name"] = df["customer_name"].astype(str).str.strip().str.title()
    else:
        df["customer_name"] = "Walk-in"

    if "extra_charges" not in df.columns:
        df["extra_charges"] = 0.0

    # Compute duration if missing
    if "duration_hours" not in df.columns and {"start_hour", "end_hour"}.issubset(df.columns):
        df["duration_hours"] = (df["end_hour"] - df["start_hour"]).clip(lower=0.5)

    if "room_type" in df.columns:
        df["room_type"] = df["room_type"].astype(str).str.strip().str.title()

    # Deduplicate
    if "booking_id" in df.columns:
        df = df.drop_duplicates(subset=["booking_id"], keep="first")

    dropped = original_len - len(df)
    if dropped:
        logger.warning("  %s: dropped %d invalid row(s).", label, dropped)

    return df.reset_index(drop=True)


# -- Public API ---------------------------------------------------------------

def validate_and_clean(files: list[ExtractedFile]) -> list[ExtractedFile]:
    """
    Run validation & cleaning on every extracted file.

    Modifies each ExtractedFile.dataframe in-place and returns
    the same list (files with zero valid rows are removed).
    """
    logger.info("-- Validation & Cleaning --")
    cleaned: list[ExtractedFile] = []

    for ef in files:
        label = f"{ef.branch_name}/{ef.filepath.name}"

        if ef.data_type == "sales":
            ef.dataframe = _validate_sales(ef.dataframe, label)
        elif ef.data_type == "bookings":
            ef.dataframe = _validate_bookings(ef.dataframe, label)
        else:
            logger.warning("  Unknown data type '%s' for %s — skipping.", ef.data_type, label)
            continue

        if ef.dataframe.empty:
            logger.warning("  %s: all rows dropped — skipping file.", label)
            continue

        logger.info(
            "  Validated %-12s | %-30s | %d clean rows",
            ef.data_type, label, len(ef.dataframe),
        )
        cleaned.append(ef)

    logger.info("Validation complete — %d file(s) with valid data.", len(cleaned))
    return cleaned

