"""
Step 1: EXTRACT — Scan raw_branch_data/ and load CSV/Excel files into DataFrames.

Each branch has its own subfolder. File naming convention:
  - sales_YYYY-MM.csv     → Sales transactions
  - bookings_YYYY-MM.csv  → Room booking records

The extractor infers the branch name and data type from
the folder name and file prefix, then returns a list of
(metadata, DataFrame) tuples for downstream processing.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from config.settings import BRANCH_MAP, RAW_DATA_DIR
from utils.file_tracker import is_processed
from utils.logger import logger


@dataclass
class ExtractedFile:
    """Metadata + raw DataFrame for a single ingested file."""

    filepath: Path
    branch_folder: str
    branch_name: str
    data_type: str          # "sales" or "bookings"
    period: str             # e.g. "2024-01"
    dataframe: pd.DataFrame


def _infer_data_type(filename: str) -> str | None:
    """Determine data type from filename prefix."""
    name = filename.lower()
    if name.startswith("sales"):
        return "sales"
    if name.startswith("booking"):
        return "bookings"
    return None


def _infer_period(filename: str) -> str:
    """Extract date period (YYYY-MM) from filename like 'sales_2024-01.csv'."""
    stem = Path(filename).stem          # e.g. "sales_2024-01"
    parts = stem.split("_", maxsplit=1)
    return parts[1] if len(parts) > 1 else "unknown"


def _read_file(filepath: Path) -> pd.DataFrame:
    """Read a CSV or Excel file into a DataFrame."""
    suffix = filepath.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(filepath, encoding="utf-8-sig")
    if suffix in (".xlsx", ".xls"):
        return pd.read_excel(filepath, engine="openpyxl")
    raise ValueError(f"Unsupported file format: {suffix}")


def extract_all_files(
    data_dir: Path | None = None,
    force: bool = False,
    branch_filter: str | None = None,
) -> list[ExtractedFile]:
    """
    Scan raw_branch_data/ and load all new files.

    Parameters
    ----------
    data_dir : Path, optional
        Override the default RAW_DATA_DIR.
    force : bool
        If True, re-process even already-ingested files.
    branch_filter : str, optional
        Only process files from this branch folder name.

    Returns
    -------
    list[ExtractedFile]
        One entry per successfully loaded file.
    """
    root = data_dir or RAW_DATA_DIR
    if not root.exists():
        logger.warning("Raw data directory does not exist: %s", root)
        return []

    results: list[ExtractedFile] = []

    for branch_dir in sorted(root.iterdir()):
        if not branch_dir.is_dir():
            continue

        folder_name = branch_dir.name
        if branch_filter and folder_name != branch_filter:
            continue

        branch_info = BRANCH_MAP.get(folder_name)
        if not branch_info:
            logger.warning("Unknown branch folder '%s' — skipping.", folder_name)
            continue

        for filepath in sorted(branch_dir.iterdir()):
            if filepath.is_dir():
                continue
            if filepath.suffix.lower() not in (".csv", ".xlsx", ".xls"):
                continue

            # Skip already-processed files unless forced
            if not force and is_processed(filepath):
                logger.debug("Skipping (already processed): %s", filepath.name)
                continue

            data_type = _infer_data_type(filepath.name)
            if data_type is None:
                logger.warning(
                    "Cannot determine data type for '%s' — skipping.", filepath.name
                )
                continue

            try:
                df = _read_file(filepath)
                logger.info(
                    "Extracted  %-12s | %-24s | %d rows",
                    data_type,
                    filepath.name,
                    len(df),
                )
                results.append(
                    ExtractedFile(
                        filepath=filepath,
                        branch_folder=folder_name,
                        branch_name=branch_info["branch_name"],
                        data_type=data_type,
                        period=_infer_period(filepath.name),
                        dataframe=df,
                    )
                )
            except Exception as exc:
                logger.error("Failed to read %s: %s", filepath, exc)

    logger.info("Extraction complete — %d file(s) loaded.", len(results))
    return results

