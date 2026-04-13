"""
logger.py

Central logging configuration for the FAERS dashboard.

Call `get_logger(__name__)` at the top of every module:

    from logger import get_logger
    log = get_logger(__name__)

Logs go to:
  - stderr (always)
  - dashboard/faers_dashboard.log (rotating, 5 MB × 3 backups)

Set env var LOG_LEVEL=DEBUG for verbose output (default: INFO).
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler

_LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
_LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "faers_dashboard.log")

_FMT = "%(asctime)s  %(levelname)-8s  %(name)-30s  %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"

_configured = False


def _configure() -> None:
    global _configured
    if _configured:
        return
    _configured = True

    root = logging.getLogger("faers")
    root.setLevel(_LOG_LEVEL)

    if root.handlers:
        return  # already set up (e.g. pytest re-import)

    formatter = logging.Formatter(_FMT, datefmt=_DATEFMT)

    # Console handler
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    # Rotating file handler (survives Streamlit reruns)
    try:
        fh = RotatingFileHandler(_LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3)
        fh.setFormatter(formatter)
        root.addHandler(fh)
    except OSError:
        root.warning("Could not open log file %s — logging to console only", _LOG_FILE)


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the 'faers' hierarchy."""
    _configure()
    # Strip the package prefix so names stay short in the log
    short = name.replace("dashboard.", "").replace("views.", "views/")
    return logging.getLogger(f"faers.{short}")
