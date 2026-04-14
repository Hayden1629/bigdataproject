"""
STARTHERE.py

Build FAERS parquet tables for either a small recent dataset or the full history.

Examples
--------
python3 utils/STARTHERE.py --mode recent
python3 utils/STARTHERE.py --mode full

Environment override
--------------------
FAERS_LOAD_MODE=recent|full
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import date

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from load_faers import DATA_ROOT, load_all_quarters, load_quarters

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TABLE_NAMES = ["demo", "drug", "reac", "outc", "rpsr", "ther", "indi"]
RECENT_YEARS = 2


def _parquet_dir(mode: str) -> str:
    return os.path.join(DATA_ROOT, "parquet_recent" if mode == "recent" else "parquet")


def _recent_quarters() -> list[str]:
    today = date.today()
    y, q = today.year - 1, (today.month - 1) // 3 + 1

    quarters = []
    for _ in range(RECENT_YEARS * 4):
        quarters.append(f"{y}Q{q}")
        q -= 1
        if q == 0:
            q, y = 4, y - 1

    return sorted(quarters)


def _parquets_exist(parquet_dir: str) -> bool:
    return all(os.path.exists(os.path.join(parquet_dir, f"{t}.parquet")) for t in TABLE_NAMES)


def _raw_data_exists() -> bool:
    if not os.path.isdir(DATA_ROOT):
        return False
    return any(
        name.startswith("faers_ascii_")
        for name in os.listdir(DATA_ROOT)
        if os.path.isdir(os.path.join(DATA_ROOT, name))
    )


def _missing_quarters(quarters: list[str]) -> list[str]:
    downloaded = set(os.listdir(DATA_ROOT))
    return [q for q in quarters if not any(name.startswith(f"faers_ascii_{q}") for name in downloaded)]


def _download(start: str | None = None, end: str | None = None) -> None:
    script = os.path.join(os.path.dirname(__file__), "download_faers.sh")
    args = ["bash", script]
    if start and end:
        args += [start, end]
    label = f"{start} through {end}" if start else "all quarters"
    print(f"Downloading {label} (this may take a while)...")
    subprocess.run(args, check=True)


def _save_parquets(tables: dict[str, pd.DataFrame], parquet_dir: str) -> None:
    os.makedirs(parquet_dir, exist_ok=True)

    # ── Deduplicate demo by caseversion (FDA guidance: keep latest version per case) ──
    demo = tables["demo"].copy()
    before_dedup = len(demo)
    demo["caseversion"] = (
        pd.to_numeric(demo["caseversion"], errors="coerce").fillna(0).astype(int)
    )
    demo = demo.sort_values("caseversion").drop_duplicates("caseid", keep="last")
    print(f"  demo dedup: {before_dedup:,} → {len(demo):,} rows "
          f"(removed {before_dedup - len(demo):,} superseded case versions)")
    tables["demo"] = demo

    # ── Filter all other tables to the surviving primaryids ──
    valid_pids = set(demo["primaryid"].unique())
    for name in ["drug", "reac", "outc", "rpsr", "ther", "indi"]:
        before = len(tables[name])
        tables[name] = tables[name][tables[name]["primaryid"].isin(valid_pids)].copy()
        removed = before - len(tables[name])
        if removed:
            print(f"  {name}: removed {removed:,} rows linked to superseded cases "
                  f"-> {len(tables[name]):,} rows")

    for name, df in tables.items():
        if name in ["drug", "ther", "indi"]:
            before = len(df)
            df = df.drop_duplicates()
            after = len(df)
            if before - after:
                print(f"  Dropped {before - after:,} exact duplicates from {name} -> {after:,} rows")
            tables[name] = df
        path = os.path.join(parquet_dir, f"{name}.parquet")
        print(f"  Saving {name} ({len(tables[name]):,} rows) -> {path}")
        tables[name].to_parquet(path, index=False)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build FAERS parquet tables for recent or full data.")
    parser.add_argument(
        "--mode",
        choices=["recent", "full"],
        default=os.environ.get("FAERS_LOAD_MODE", "recent"),
        help="Use 'recent' for a smaller testing dataset or 'full' for all downloaded quarters.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild parquet files even if they already exist.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    mode = args.mode
    parquet_dir = _parquet_dir(mode)

    if mode == "recent":
        quarters = _recent_quarters()
        print(f"Recent mode: loading {quarters[0]} through {quarters[-1]}")
    else:
        quarters = []
        print("Full mode: loading all available quarters")

    if _parquets_exist(parquet_dir) and not args.force:
        print(f"Parquet files already exist in {parquet_dir}. Loading...")
        tables = {t: pd.read_parquet(os.path.join(parquet_dir, f"{t}.parquet")) for t in TABLE_NAMES}
    else:
        if mode == "recent":
            missing = _missing_quarters(quarters)
            if missing:
                _download(missing[0], missing[-1])
            print("Loading recent quarters from raw ASCII files...")
            tables = load_quarters(quarters)
        else:
            if not _raw_data_exists():
                _download()
            print("Loading all quarters from raw ASCII files...")
            tables = load_all_quarters()

        print("\nSaving to parquet...")
        _save_parquets(tables, parquet_dir)
        print("Done.")

    print("\nTable shapes:")
    for name, df in tables.items():
        print(f"  {name:6s}: {len(df):>12,} rows x {df.shape[1]} cols")

    print("\nNext steps:")
    print(f"  1. Build cache: FAERS_PARQUET_DIR={parquet_dir} python3 dashboard/precompute.py")
    print(f"  2. Run app:     FAERS_PARQUET_DIR={parquet_dir} streamlit run dashboard/app.py")


if __name__ == "__main__":
    main()
