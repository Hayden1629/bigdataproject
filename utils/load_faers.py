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
    1 case x 5 drugs x 4 reactions = 20 rows per case, all heavily duplicated.
    Keep them separate and join only what you need for a specific question.

    Example: join demo + drug to study drug demographics
        df = demo.merge(drug[["primaryid", "drugname", "role_cod"]], on="primaryid")

    Example: join demo + reac to study who gets which reactions
        df = demo.merge(reac[["primaryid", "pt"]], on="primaryid")
"""

import os
import re
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

# utils/ is one level below the project root, so go up one level to find data/
DATA_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))


def _find_txt(quarter: str, prefix: str, folder: str | None = None) -> str:
    """Locate the .txt file for a given quarter and table prefix.

    Args:
        quarter: normalized quarter string, e.g. "2018Q1"
        prefix:  file prefix, e.g. "DEMO"
        folder:  actual data folder name under DATA_ROOT (may differ from quarter
                 when FDA releases corrected zips like "faers_ascii_2018Q1_new")
    """
    year, q = quarter.split("Q")  # robust split — avoids quarter[-1] bug
    yy = year[-2:]

    folder_name = folder or f"faers_ascii_{year}Q{q}"

    # Search both the flat dir and the ascii subdir; also handle FDA "_new" filename suffix
    base = f"{prefix}{yy}Q{q}"
    base_lo = base.lower()
    ascii_dir = os.path.join(DATA_ROOT, folder_name, "ascii")
    flat_dir  = os.path.join(DATA_ROOT, folder_name)
    patterns = [
        os.path.join(ascii_dir, f"{base}.txt"),
        os.path.join(flat_dir,  f"{base}.txt"),
        os.path.join(ascii_dir, f"{base}_new.txt"),
        os.path.join(flat_dir,  f"{base}_new.txt"),
        os.path.join(ascii_dir, f"{base_lo}.txt"),
        os.path.join(flat_dir,  f"{base_lo}.txt"),
        os.path.join(ascii_dir, f"{base_lo}_new.txt"),
        os.path.join(flat_dir,  f"{base_lo}_new.txt"),
        os.path.join(ascii_dir, f"{base}*.txt"),
        os.path.join(flat_dir,  f"{base}*.txt"),
    ]
    for pattern in patterns:
        matches = glob.glob(pattern)
        if matches:
            return matches[0]

    raise FileNotFoundError(
        f"Could not find {prefix} file for {quarter}. "
        f"Run download_faers.sh first, or check DATA_ROOT={DATA_ROOT}"
    )


def load_quarter(quarter: str, tables: list[str] | None = None, folder: str | None = None) -> dict[str, pd.DataFrame]:
    """
    Load all (or selected) FAERS tables for one quarter.

    Args:
        quarter: normalized quarter string, e.g. "2025Q4"
        tables:  list of table names to load, e.g. ["demo", "drug", "reac"]
                 defaults to all 7 tables
        folder:  actual folder name under DATA_ROOT (e.g. "faers_ascii_2018Q1_new");
                 inferred from quarter when omitted

    Returns:
        dict mapping table name -> DataFrame
    """
    to_load = tables or list(FILE_PREFIXES.keys())
    result = {}

    for name in to_load:
        prefix = FILE_PREFIXES[name]
        path = _find_txt(quarter, prefix, folder)
        print(f"  Loading {name} ({quarter}) from {os.path.basename(path)} ...", end=" ", flush=True)
        df = pd.read_csv(
            path,
            sep="$",
            dtype=str,           # keep everything as str initially — mixed types everywhere
            encoding="latin-1",  # FDA files use latin-1, not utf-8
            low_memory=False,
        )
        df.columns = df.columns.str.lower().str.strip()
        df["quarter"] = quarter
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


def load_all_quarters() -> dict[str, pd.DataFrame]:
    """Load every downloaded quarter, preferring corrected (_new) versions."""
    folders = sorted(f for f in os.listdir(DATA_ROOT) if f.startswith("faers_ascii_"))

    # normalized quarter (e.g. "2018Q1") -> actual folder name on disk
    quarter_to_folder: dict[str, str] = {}
    for folder in folders:
        m = re.search(r"(\d{4}Q\d)", folder)
        if m:
            quarter = m.group(1)
            # prefer the "_new" (corrected) version when both exist
            if quarter not in quarter_to_folder or "_new" in folder:
                quarter_to_folder[quarter] = folder

    all_dfs: dict[str, list[pd.DataFrame]] = {t: [] for t in FILE_PREFIXES.keys()}
    for quarter in sorted(quarter_to_folder):
        folder = quarter_to_folder[quarter]
        print(f"Loading {quarter} (from {folder})...")
        q_data = load_quarter(quarter, folder=folder)
        for name, df in q_data.items():
            all_dfs[name].append(df)

    return {name: pd.concat(dfs, ignore_index=True) for name, dfs in all_dfs.items()}
