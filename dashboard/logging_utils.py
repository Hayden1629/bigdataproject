from __future__ import annotations

from contextlib import contextmanager
import logging
import os
import sys
import time


def setup_logging() -> None:
    level_name = os.environ.get("FAERS_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    root = logging.getLogger()
    if root.handlers:
        root.setLevel(level)
        return
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        stream=sys.stdout,
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


@contextmanager
def log_timing(logger: logging.Logger, label: str, level: int = logging.INFO):
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        logger.log(level, "%s completed in %.3fs", label, elapsed)
