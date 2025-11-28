"""
run_pipeline.py — Main entry point for the Karaoke ETL Pipeline.

Orchestrates all four ETL steps:
  1. EXTRACT   → scan & load raw CSV/Excel files
  2. VALIDATE  → data quality checks & cleaning
  3. TRANSFORM → map to Star Schema (dimensions + facts)
  4. LOAD      → write to PostgreSQL database

Usage:
    python run_pipeline.py                    # Full run
    python run_pipeline.py --dry-run          # Validate without loading
    python run_pipeline.py --force-reload     # Re-process all files
    python run_pipeline.py --branch branch_hcm  # Process single branch
"""

from __future__ import annotations

import argparse
import time
import sys

from config.settings import RAW_DATA_DIR
from etl.extract import extract_all_files
from etl.validate import validate_and_clean
from etl.transform import transform_to_star_schema
from etl.load import load_to_database
from utils.file_tracker import reset_tracker
from utils.logger import logger


def run_pipeline(
    dry_run: bool = False,
    force: bool = False,
    branch: str | None = None,
) -> None:
    """Execute the full ETL pipeline."""
    start_time = time.time()

    logger.info("=" * 60)
    logger.info("  KARAOKE ETL PIPELINE — Starting")
    logger.info("  Mode: %s", "DRY RUN" if dry_run else "LIVE")
    if branch:
        logger.info("  Branch filter: %s", branch)
    logger.info("=" * 60)

    # -- Force reload: clear tracking history -----------------------------
    if force:
        reset_tracker()

    # -- Step 1: EXTRACT --------------------------------------------------
    logger.info("")
    logger.info("-- Step 1: EXTRACT --")
    files = extract_all_files(
        data_dir=RAW_DATA_DIR,
        force=force,
        branch_filter=branch,
    )

    if not files:
        logger.info("No new files to process. Pipeline finished.")
        return

    # -- Step 2: VALIDATE & CLEAN -----------------------------------------
    logger.info("")
    logger.info("-- Step 2: VALIDATE & CLEAN --")
    cleaned = validate_and_clean(files)

    if not cleaned:
        logger.warning("All files failed validation. Pipeline finished.")
        return

    # -- Step 3: TRANSFORM ------------------------------------------------
    logger.info("")
    logger.info("-- Step 3: TRANSFORM --")
    schema = transform_to_star_schema(cleaned)

    # -- Step 4: LOAD -----------------------------------------------------
    logger.info("")
    logger.info("-- Step 4: LOAD --")
    counts = load_to_database(schema, files=cleaned, dry_run=dry_run)

    # -- Summary ----------------------------------------------------------
    elapsed = time.time() - start_time
    logger.info("")
    logger.info("=" * 60)
    logger.info("  PIPELINE COMPLETE")
    logger.info("  Time elapsed: %.1f seconds", elapsed)
    logger.info("  Files processed: %d", len(cleaned))
    for table, count in counts.items():
        logger.info("    %-16s | %d rows", table, count)
    logger.info("  Total rows: %d", sum(counts.values()))
    logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Karaoke Multi-Branch ETL Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_pipeline.py                      # Process all new files
  python run_pipeline.py --dry-run            # Validate without loading to DB
  python run_pipeline.py --force-reload       # Re-process everything
  python run_pipeline.py --branch branch_hcm  # Process one branch only
        """,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run extraction, validation, and transformation but skip database loading.",
    )
    parser.add_argument(
        "--force-reload",
        action="store_true",
        help="Ignore processing history and re-ingest all files.",
    )
    parser.add_argument(
        "--branch",
        type=str,
        default=None,
        help="Only process files from this branch folder (e.g., branch_hcm).",
    )

    args = parser.parse_args()

    try:
        run_pipeline(
            dry_run=args.dry_run,
            force=args.force_reload,
            branch=args.branch,
        )
    except KeyboardInterrupt:
        logger.info("Pipeline interrupted by user.")
        sys.exit(1)
    except Exception as exc:
        logger.error("Pipeline failed: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
