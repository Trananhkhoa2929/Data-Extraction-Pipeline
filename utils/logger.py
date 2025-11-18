"""
Structured logging for the ETL pipeline.

Provides a pre-configured logger with colored console output
and optional file output for production debugging.
"""

import logging
import sys
from config.settings import LOG_LEVEL


def _setup_logger(name: str = "etl_pipeline") -> logging.Logger:
    """Create and configure the pipeline logger."""
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    # -- Console handler --------------------------------------------------
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console.setFormatter(fmt)
    logger.addHandler(console)

    # Prevent duplicate logs if root logger also has handlers
    logger.propagate = False

    return logger


logger = _setup_logger()
