"""
STARTHERE.py

One-run setup for the FAERS dataset.

Set LOW_RAM = True to load only the last 2 years (faster, smaller files).
Set LOW_RAM = False to load the full history (2012Q4 - present).

What this does:
  1. Checks if parquet files already exist -> if so, loads them and exits early
  2. Checks if raw FAERS data is downloaded -> if not, runs download_faers.sh
  3. Loads quarters into DataFrames via load_faers
  4. Saves each table as a parquet file for fast future access

Output parquet files:
    LOW_RAM = True  -> data/parquet_recent/
    LOW_RAM = False -> data/parquet/

Tables:
    demo.parquet  - 1 row per case (demographics + admin info)
    drug.parquet  - 1+ rows per case (drug/biologic info)
    reac.parquet  - 1+ rows per case (adverse event MedDRA terms)
    outc.parquet  - 0+ rows per case (patient outcomes)
    rpsr.parquet  - 0+ rows per case (report sources)
    ther.parquet  - 0+ rows per drug per case (therapy dates)
    indi.parquet  - 0+ rows per drug per case (drug indications)
"""

# --- Change this to True for testing / smaller machines ---
LOW_RAM = True  # True = last 2 years only; False = full history (2012Q4 - present)
RECENT_YEARS = 2  # only used when LOW_RAM = True

import os
import sys
import subprocess
import pandas as pd
from datetime import date

# Make sure load_faers (in the same utils/ folder) is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from load_faers import load_all_quarters, load_quarters, DATA_ROOT

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PARQUET_DIR  = os.path.join(DATA_ROOT, "parquet_recent" if LOW_RAM else "parquet")
TABLE_NAMES  = ["demo", "drug", "reac", "outc", "rpsr", "ther", "indi"]


def _recent_quarters() -> list[str]:
    today = date.today()

    # Start from last year — FAERS quarters are published with a lag,
    # so using today's year risks requesting a quarter that isn't out yet.
    # (today.month - 1) // 3 + 1 converts month -> quarter:
    #   Jan-Mar=1, Apr-Jun=2, Jul-Sep=3, Oct-Dec=4
    y, q = today.year - 1, (today.month - 1) // 3 + 1

    quarters = []
    for _ in range(RECENT_YEARS * 4):  # 4 quarters per year
        quarters.append(f"{y}Q{q}")
        q -= 1
        if q == 0:          # rolled past Q1 — go back one year and reset to Q4
            q, y = 4, y - 1

    return sorted(quarters)  # oldest first


def _parquets_exist() -> bool:
    return all(os.path.exists(os.path.join(PARQUET_DIR, f"{t}.parquet")) for t in TABLE_NAMES)


def _raw_data_exists() -> bool:
    if not os.path.isdir(DATA_ROOT):
        return False
    return any(
        f.startswith("faers_ascii_")
        for f in os.listdir(DATA_ROOT)
        if os.path.isdir(os.path.join(DATA_ROOT, f))
    )


def _missing_quarters(quarters: list[str]) -> list[str]:
    downloaded = set(os.listdir(DATA_ROOT))
    return [q for q in quarters if not any(f.startswith(f"faers_ascii_{q}") for f in downloaded)]


def _download(start: str | None = None, end: str | None = None):
    script = os.path.join(os.path.dirname(__file__), "download_faers.sh")
    args = ["bash", script]
    if start and end:
        args += [start, end]
    label = f"{start} through {end}" if start else "all quarters"
    print(f"Downloading {label} (this may take a while)...")
    subprocess.run(args, check=True)


def _save_parquets(tables: dict[str, pd.DataFrame]):
    os.makedirs(PARQUET_DIR, exist_ok=True)
    for name, df in tables.items():
        #delete duplicates from drug, therm and indi tables
        if name in ["drug", "ther", "indi"]:
            before = len(df)
            df.drop_duplicates(inplace=True)
            after = len(df)
            print(f"  Dropped {before - after:,} duplicates from {name} -> {after:,} rows")
        path = os.path.join(PARQUET_DIR, f"{name}.parquet")
        print(f"  Saving {name} ({len(df):,} rows) -> {path}")
        df.to_parquet(path, index=False)


if __name__ == "__main__":
    if LOW_RAM:
        quarters = _recent_quarters()
        print(f"LOW_RAM mode: loading {quarters[0]} through {quarters[-1]}")
    else:
        print("Full mode: loading all available quarters")

    if _parquets_exist():
        print(f"Parquet files already exist in {PARQUET_DIR}. Loading...")
        tables = {t: pd.read_parquet(os.path.join(PARQUET_DIR, f"{t}.parquet")) for t in TABLE_NAMES}
    else:
        if LOW_RAM:
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
        _save_parquets(tables)
        print("Done.")

    print("\nTable shapes:")
    for name, df in tables.items():
        print(f"  {name:6s}: {len(df):>12,} rows x {df.shape[1]} cols")
