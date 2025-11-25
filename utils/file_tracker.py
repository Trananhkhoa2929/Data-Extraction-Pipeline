"""
File tracker — records which raw data files have been successfully
processed so the pipeline skips them on subsequent runs.

The state is persisted to a JSON file (processed_files.json).
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from config.settings import PROCESSED_LOG
from utils.logger import logger


def _load_log() -> dict[str, str]:
    """Load the processed-files log from disk."""
    if PROCESSED_LOG.exists():
        with open(PROCESSED_LOG, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_log(log: dict[str, str]) -> None:
    """Persist the processed-files log to disk."""
    with open(PROCESSED_LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)


def is_processed(filepath: Path) -> bool:
    """Check whether a file has already been successfully ingested."""
    log = _load_log()
    return str(filepath) in log


def mark_processed(filepath: Path) -> None:
    """Record that a file has been successfully ingested."""
    log = _load_log()
    log[str(filepath)] = datetime.now(timezone.utc).isoformat()
    _save_log(log)
    logger.debug("Marked as processed: %s", filepath.name)


def reset_tracker() -> None:
    """Clear all processing history (for --force-reload)."""
    if PROCESSED_LOG.exists():
        PROCESSED_LOG.unlink()
        logger.info("Processing history cleared.")
