"""
load_faers.py

Loads one or more FAERS ASCII quarterly extracts into 7 separate DataFrames.
The relational structure (linked by primaryid) is preserved — do NOT flatten
everything into one table (see comments below).

Usage:
    from load_faers import load_quarter, load_quarters

    # Single quarter
    tables = load_quarter("2025Q4")

    # Multiple quarters stacked (e.g. for multi-year analysis)
    tables = load_quarters(["2023Q1", "2023Q2", "2023Q3", "2023Q4"])

    # Access individual tables
    demo = tables["demo"]   # 1 row per case
    drug = tables["drug"]   # 1+ rows per case
    reac = tables["reac"]   # 1+ rows per case
    outc = tables["outc"]   # 0+ rows per case
    rpsr = tables["rpsr"]   # 0+ rows per case
    ther = tables["ther"]   # 0+ rows per drug per case
    indi = tables["indi"]   # 0+ rows per drug per case

WHY NOT ONE FLAT DATAFRAME?
    DEMO has 1 row per case. DRUG has 4-5 rows per case on average. REAC has
    3-4 rows per case on average. A full outer join would multiply rows:
    1 case × 5 drugs × 4 reactions = 20 rows per case, all heavily duplicated.
    Keep them separate and join only what you need for a specific question.

    Example: join demo + drug to study drug demographics
        df = demo.merge(drug[["primaryid", "drugname", "role_cod"]], on="primaryid")

    Example: join demo + reac to study who gets which reactions
        df = demo.merge(reac[["primaryid", "pt"]], on="primaryid")
"""

import os
import glob
import pandas as pd

# Map table short name -> file prefix
FILE_PREFIXES = {
    "demo": "DEMO",
    "drug": "DRUG",
    "reac": "REAC",
    "outc": "OUTC",
    "rpsr": "RPSR",
    "ther": "THER",
    "indi": "INDI",
}

DATA_ROOT = os.path.join(os.path.dirname(__file__), "data")


def _find_txt(quarter: str, prefix: str) -> str:
    """Locate the .txt file for a given quarter and table prefix."""
    year = quarter[:4]  # e.g. "2025"
    q = quarter[-1]     # e.g. "4"
    yy = year[-2:]      # e.g. "25"

    # Search both the flat dir and the ASCII subdir
    patterns = [
        os.path.join(DATA_ROOT, f"faers_ascii_{year}Q{q}", "ASCII", f"{prefix}{yy}Q{q}.txt"),
        os.path.join(DATA_ROOT, f"faers_ascii_{year}Q{q}", f"{prefix}{yy}Q{q}.txt"),
    ]
    for pattern in patterns:
        matches = glob.glob(pattern)
        if matches:
            return matches[0]

    raise FileNotFoundError(
        f"Could not find {prefix} file for {quarter}. "
        f"Run download_faers.sh first, or check DATA_ROOT={DATA_ROOT}"
    )


def load_quarter(quarter: str, tables: list[str] | None = None) -> dict[str, pd.DataFrame]:
    """
    Load all (or selected) FAERS tables for one quarter.

    Args:
        quarter: e.g. "2025Q4"
        tables:  list of table names to load, e.g. ["demo", "drug", "reac"]
                 defaults to all 7 tables

    Returns:
        dict mapping table name -> DataFrame
    """
    to_load = tables or list(FILE_PREFIXES.keys())
    result = {}

    for name in to_load:
        prefix = FILE_PREFIXES[name]
        path = _find_txt(quarter, prefix)
        print(f"  Loading {name} ({quarter}) from {os.path.basename(path)} ...", end=" ", flush=True)
        df = pd.read_csv(
            path,
            sep="$",
            dtype=str,           # keep everything as str initially — mixed types everywhere
            encoding="latin-1",  # FDA files use latin-1, not utf-8
            low_memory=False,
        )
        # Normalize column names to lowercase
        df.columns = df.columns.str.lower().str.strip()
        df["quarter"] = quarter  # tag source quarter for multi-quarter stacks
        print(f"{len(df):,} rows")
        result[name] = df

    return result


def load_quarters(quarters: list[str], tables: list[str] | None = None) -> dict[str, pd.DataFrame]:
    """
    Load and vertically stack multiple quarters into one set of DataFrames.

    Args:
        quarters: list of quarter strings, e.g. ["2024Q1", "2024Q2", "2024Q3", "2024Q4"]
        tables:   subset of tables to load (default: all 7)

    Returns:
        dict mapping table name -> DataFrame (all quarters stacked)
    """
    all_dfs: dict[str, list[pd.DataFrame]] = {t: [] for t in (tables or FILE_PREFIXES.keys())}

    for quarter in quarters:
        print(f"Loading {quarter}...")
        q_data = load_quarter(quarter, tables)
        for name, df in q_data.items():
            all_dfs[name].append(df)

    return {name: pd.concat(dfs, ignore_index=True) for name, dfs in all_dfs.items()}


if __name__ == "__main__":
    # Quick demo: load 2025Q4 and print shape of each table
    print("Loading 2025Q4...")
    tables = load_quarter("2025Q4")

    print("\nTable shapes:")
    for name, df in tables.items():
        print(f"  {name:6s}: {df.shape[0]:>10,} rows × {df.shape[1]} cols")

    print("\nDEMO columns:", list(tables["demo"].columns))
    print("DRUG columns:", list(tables["drug"].columns))
    print("REAC columns:", list(tables["reac"].columns))
