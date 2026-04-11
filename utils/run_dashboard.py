"""
Run the Streamlit dashboard against either the recent or full parquet dataset.

Examples
--------
python3 utils/run_dashboard.py --mode recent
python3 utils/run_dashboard.py --mode full
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_ROOT = os.path.join(PROJECT_ROOT, "data")
DASHBOARD_ROOT = os.path.join(PROJECT_ROOT, "dashboard")


def _paths_for_mode(mode: str) -> tuple[str, str]:
    parquet_dir = os.path.join(DATA_ROOT, "parquet_recent" if mode == "recent" else "parquet")
    cache_dir = os.path.join(DASHBOARD_ROOT, "cache_recent" if mode == "recent" else "cache_full")
    return parquet_dir, cache_dir


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the FAERS dashboard with recent or full data.")
    parser.add_argument("--mode", choices=["recent", "full"], default="recent")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    parquet_dir, cache_dir = _paths_for_mode(args.mode)

    env = os.environ.copy()
    env["FAERS_PARQUET_DIR"] = parquet_dir
    env["FAERS_CACHE_DIR"] = cache_dir

    if not os.path.isdir(parquet_dir):
        raise SystemExit(
            f"Parquet directory not found: {parquet_dir}\n"
            f"Build it first with: python3 utils/STARTHERE.py --mode {args.mode}"
        )

    if not os.path.isdir(cache_dir):
        print(
            f"Warning: cache directory {cache_dir} does not exist yet.\n"
            f"Build it with: FAERS_PARQUET_DIR={parquet_dir} FAERS_CACHE_DIR={cache_dir} python3 dashboard/precompute.py\n"
        )

    cmd = ["streamlit", "run", os.path.join(DASHBOARD_ROOT, "app.py")]
    subprocess.run(cmd, check=True, env=env)


if __name__ == "__main__":
    main()
