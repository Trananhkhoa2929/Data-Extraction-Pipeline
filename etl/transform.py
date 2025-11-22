"""
Step 3: TRANSFORM — Map cleaned flat data into Star Schema structures.

Produces DataFrames ready for loading into:
  • dim_branch, dim_service, dim_room, dim_time
  • fact_sales, fact_bookings
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd
import numpy as np

from config.settings import BRANCH_MAP, ROOM_TYPES
from etl.extract import ExtractedFile
from utils.logger import logger


@dataclass
class StarSchemaData:
    """Container for all dimension and fact DataFrames."""

    dim_branch: pd.DataFrame = field(default_factory=pd.DataFrame)
    dim_service: pd.DataFrame = field(default_factory=pd.DataFrame)
    dim_room: pd.DataFrame = field(default_factory=pd.DataFrame)
    dim_time: pd.DataFrame = field(default_factory=pd.DataFrame)
    fact_sales: pd.DataFrame = field(default_factory=pd.DataFrame)
    fact_bookings: pd.DataFrame = field(default_factory=pd.DataFrame)


# -- Dimension builders -------------------------------------------------------

_HOLIDAYS_VN = {
    (1, 1), (4, 30), (5, 1), (9, 2),  # Fixed public holidays
}


def _build_dim_time(dates: pd.Series) -> pd.DataFrame:
    """Create a date-dimension from a series of dates."""
    unique_dates = pd.to_datetime(dates.dropna().unique())
    records = []
    for dt in sorted(unique_dates):
        records.append({
            "full_date": dt.date(),
            "day_of_week": dt.dayofweek,        # 0=Mon … 6=Sun
            "day_name": dt.strftime("%A"),
            "month": dt.month,
            "month_name": dt.strftime("%B"),
            "quarter": (dt.month - 1) // 3 + 1,
            "year": dt.year,
            "is_weekend": dt.dayofweek >= 5,
            "is_holiday": (dt.month, dt.day) in _HOLIDAYS_VN,
        })
    return pd.DataFrame(records)


def _build_dim_branch(branch_folders: set[str]) -> pd.DataFrame:
    """Build branch dimension from the folders we actually processed."""
    records = []
    for idx, folder in enumerate(sorted(branch_folders), start=1):
        info = BRANCH_MAP.get(folder)
        if info is None:
            continue
        records.append({
            "branch_id": f"br_{idx}",
            **info,
        })
    return pd.DataFrame(records)


def _build_dim_service(sales_dfs: list[pd.DataFrame]) -> pd.DataFrame:
    """Extract unique services from all sales data."""
    if not sales_dfs:
        return pd.DataFrame()

    combined = pd.concat(sales_dfs, ignore_index=True)
    needed_cols = {"service_name", "category", "unit_price"}
    if not needed_cols.issubset(combined.columns):
        logger.warning("Sales data missing service columns — dim_service will be empty.")
        return pd.DataFrame()

    services = (
        combined[["service_name", "category", "unit_price"]]
        .drop_duplicates(subset=["service_name"])
        .reset_index(drop=True)
    )
    services.insert(0, "service_id", [f"svc_{i+1}" for i in range(len(services))])
    services["unit"] = "item"
    return services


def _build_dim_room(bookings_dfs: list[pd.DataFrame], dim_branch: pd.DataFrame) -> pd.DataFrame:
    """Extract unique rooms from all booking data and link to branch keys."""
    if not bookings_dfs:
        return pd.DataFrame()

    combined = pd.concat(bookings_dfs, ignore_index=True)
    needed_cols = {"room_id", "room_name", "room_type", "branch_name"}
    if not needed_cols.issubset(combined.columns):
        logger.warning("Booking data missing room columns — dim_room will be empty.")
        return pd.DataFrame()

    rooms = (
        combined[["room_id", "room_name", "room_type", "branch_name"]]
        .drop_duplicates(subset=["room_id"])
        .reset_index(drop=True)
    )

    # Map branch_name → branch_key (positional index in dim_branch)
    branch_key_map = dict(zip(dim_branch["branch_name"], range(1, len(dim_branch) + 1)))
    rooms["branch_key"] = rooms["branch_name"].map(branch_key_map)

    # Enrich with capacity and hourly_rate from ROOM_TYPES
    rooms["capacity"] = rooms["room_type"].map(
        lambda rt: ROOM_TYPES.get(rt, {}).get("capacity", 10)
    )
    rooms["hourly_rate"] = rooms["room_type"].map(
        lambda rt: ROOM_TYPES.get(rt, {}).get("hourly_rate", 200_000)
    )

    return rooms[["room_id", "branch_key", "room_name", "room_type", "capacity", "hourly_rate"]]


# -- Fact builders ------------------------------------------------------------

def _build_fact_sales(
    sales_files: list[ExtractedFile],
    dim_branch: pd.DataFrame,
    dim_service: pd.DataFrame,
    dim_time: pd.DataFrame,
) -> pd.DataFrame:
    """Map cleaned sales data to fact_sales with surrogate keys."""
    if not sales_files:
        return pd.DataFrame()

    dfs = []
    for ef in sales_files:
        df = ef.dataframe.copy()
        df["branch_name"] = ef.branch_name
        dfs.append(df)

    combined = pd.concat(dfs, ignore_index=True)

    # Build lookup maps
    branch_map = dict(zip(dim_branch["branch_name"], range(1, len(dim_branch) + 1)))
    service_map = dict(zip(dim_service["service_name"], range(1, len(dim_service) + 1)))

    # Map full_date → time_key
    time_dates = pd.to_datetime(dim_time["full_date"])
    time_map = dict(zip(time_dates.dt.date, range(1, len(dim_time) + 1)))

    combined["branch_key"] = combined["branch_name"].map(branch_map)
    combined["service_key"] = combined["service_name"].map(service_map)
    combined["time_key"] = pd.to_datetime(combined["date"]).dt.date.map(time_map)

    # Drop rows that couldn't be mapped
    combined = combined.dropna(subset=["branch_key", "service_key", "time_key"])
    combined["branch_key"] = combined["branch_key"].astype(int)
    combined["service_key"] = combined["service_key"].astype(int)
    combined["time_key"] = combined["time_key"].astype(int)

    return combined[[
        "branch_key", "service_key", "time_key",
        "transaction_id", "quantity", "unit_price",
        "discount_amount", "total_amount", "payment_method",
    ]].reset_index(drop=True)


def _build_fact_bookings(
    booking_files: list[ExtractedFile],
    dim_branch: pd.DataFrame,
    dim_room: pd.DataFrame,
    dim_time: pd.DataFrame,
) -> pd.DataFrame:
    """Map cleaned booking data to fact_bookings with surrogate keys."""
    if not booking_files:
        return pd.DataFrame()

    dfs = []
    for ef in booking_files:
        df = ef.dataframe.copy()
        df["branch_name"] = ef.branch_name
        dfs.append(df)

    combined = pd.concat(dfs, ignore_index=True)

    branch_map = dict(zip(dim_branch["branch_name"], range(1, len(dim_branch) + 1)))
    room_map = dict(zip(dim_room["room_id"], range(1, len(dim_room) + 1)))
    time_dates = pd.to_datetime(dim_time["full_date"])
    time_map = dict(zip(time_dates.dt.date, range(1, len(dim_time) + 1)))

    combined["branch_key"] = combined["branch_name"].map(branch_map)
    combined["room_key"] = combined["room_id"].map(room_map)
    combined["time_key"] = pd.to_datetime(combined["date"]).dt.date.map(time_map)

    combined = combined.dropna(subset=["branch_key", "room_key", "time_key"])
    combined["branch_key"] = combined["branch_key"].astype(int)
    combined["room_key"] = combined["room_key"].astype(int)
    combined["time_key"] = combined["time_key"].astype(int)

    return combined[[
        "branch_key", "room_key", "time_key",
        "booking_id", "customer_name",
        "start_hour", "end_hour", "duration_hours",
        "num_guests", "room_fee", "extra_charges", "total_charge",
    ]].reset_index(drop=True)


# -- Public API ---------------------------------------------------------------

def transform_to_star_schema(files: list[ExtractedFile]) -> StarSchemaData:
    """
    Transform cleaned flat data into a Star Schema.

    Returns a StarSchemaData container with all dimension and fact DataFrames.
    """
    logger.info("-- Transformation (Star Schema) --")

    sales_files = [f for f in files if f.data_type == "sales"]
    booking_files = [f for f in files if f.data_type == "bookings"]
    branch_folders = {f.branch_folder for f in files}

    # Collect all dates for dim_time
    all_dates = pd.concat(
        [f.dataframe["date"] for f in files if "date" in f.dataframe.columns],
        ignore_index=True,
    )

    # Build dimensions
    dim_time = _build_dim_time(all_dates)
    dim_branch = _build_dim_branch(branch_folders)
    dim_service = _build_dim_service([f.dataframe for f in sales_files])
    dim_room = _build_dim_room(
        [f.dataframe.assign(branch_name=f.branch_name) for f in booking_files],
        dim_branch,
    )

    # Build facts
    fact_sales = _build_fact_sales(sales_files, dim_branch, dim_service, dim_time)
    fact_bookings = _build_fact_bookings(booking_files, dim_branch, dim_room, dim_time)

    result = StarSchemaData(
        dim_branch=dim_branch,
        dim_service=dim_service,
        dim_room=dim_room,
        dim_time=dim_time,
        fact_sales=fact_sales,
        fact_bookings=fact_bookings,
    )

    for name in ["dim_branch", "dim_service", "dim_room", "dim_time", "fact_sales", "fact_bookings"]:
        df = getattr(result, name)
        logger.info("  %-16s | %d rows", name, len(df))

    logger.info("Transformation complete.")
    return result

