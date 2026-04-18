#!/usr/bin/env python3
"""
One-step FAERS dashboard bootstrap (Windows + macOS + Linux).

What it does (idempotent):
1) Optionally install Python dependencies
2) Ensure FAERS raw quarter folders exist (download missing ZIPs)
3) Build parquet tables (recent/full)
4) Build dashboard cache tables
5) Optionally launch Streamlit

Examples:
  python utils/setup_dashboard.py --mode recent --run
  python utils/setup_dashboard.py --mode full
  python utils/setup_dashboard.py --mode recent --skip-deps
  python utils/setup_dashboard.py --mode recent --force-parquet --force-cache
"""

from __future__ import annotations

import argparse
import io
import os
import re
import subprocess
import sys
import time
import zipfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
DASHBOARD_DIR = PROJECT_ROOT / "dashboard"
FDA_EXPORT_BASE = "https://fis.fda.gov/content/Exports"
TABLES = ("demo", "drug", "reac", "outc", "rpsr", "ther", "indi")


@dataclass(frozen=True)
class ModePaths:
    mode: str
    parquet_dir: Path
    cache_dir: Path


def _log(msg: str) -> None:
    print(msg, flush=True)


def _run(cmd: list[str], env: dict[str, str] | None = None) -> None:
    _log(f"$ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT), env=env, check=False)
    if result.returncode != 0:
        raise SystemExit(f"Command failed (exit {result.returncode}): {' '.join(cmd)}")


def _mode_paths(mode: str) -> ModePaths:
    if mode == "recent":
        return ModePaths(
            mode, DATA_DIR / "parquet_recent", DASHBOARD_DIR / "cache_recent"
        )
    return ModePaths(mode, DATA_DIR / "parquet", DASHBOARD_DIR / "cache_full")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Idempotent one-step FAERS dashboard setup."
    )
    parser.add_argument("--mode", choices=["recent", "full"], default="recent")
    parser.add_argument(
        "--skip-deps", action="store_true", help="Skip pip install -r requirements.txt"
    )
    parser.add_argument(
        "--force-download",
        action="store_true",
        help="Re-download quarter ZIPs even if extracted folder exists",
    )
    parser.add_argument(
        "--force-parquet",
        action="store_true",
        help="Rebuild parquet files even if they already exist",
    )
    parser.add_argument(
        "--force-cache",
        action="store_true",
        help="Rebuild dashboard cache files even if they already exist",
    )
    parser.add_argument(
        "--run", action="store_true", help="Launch Streamlit after setup"
    )
    parser.add_argument(
        "--start-quarter",
        default=None,
        help="Optional quarter lower bound (e.g. 2023Q1)",
    )
    parser.add_argument(
        "--end-quarter", default=None, help="Optional quarter upper bound (e.g. 2025Q4)"
    )
    return parser.parse_args()


def _install_dependencies(skip: bool) -> None:
    if skip:
        _log("Skipping dependency installation (--skip-deps).")
        return
    req = PROJECT_ROOT / "requirements.txt"
    if not req.exists():
        raise SystemExit(f"Missing requirements file: {req}")
    _log("Installing dependencies from requirements.txt...")
    _run([sys.executable, "-m", "pip", "install", "-r", str(req)])


def _quarter_key(q: str) -> tuple[int, int]:
    m = re.fullmatch(r"(\d{4})Q([1-4])", q)
    if not m:
        raise ValueError(f"Invalid quarter format: {q} (expected YYYYQ1-YYYYQ4)")
    return int(m.group(1)), int(m.group(2))


def _all_quarters(start: str = "2012Q4", end: str | None = None) -> list[str]:
    if end is None:
        today = date.today()
        end = f"{today.year}Q{((today.month - 1) // 3) + 1}"

    sy, sq = _quarter_key(start)
    ey, eq = _quarter_key(end)
    if (sy, sq) > (ey, eq):
        raise ValueError(f"Start quarter {start} is after end quarter {end}")

    out: list[str] = []
    y, q = sy, sq
    while (y, q) <= (ey, eq):
        out.append(f"{y}Q{q}")
        q += 1
        if q == 5:
            y += 1
            q = 1
    return out


def _recent_quarters(n_years: int = 2) -> list[str]:
    today = date.today()
    y = today.year
    q = ((today.month - 1) // 3) + 1
    out: list[str] = []
    for _ in range(n_years * 4):
        out.append(f"{y}Q{q}")
        q -= 1
        if q == 0:
            y -= 1
            q = 4
    return sorted(out)


def _quarter_folder_candidates(quarter: str) -> list[Path]:
    return [
        DATA_DIR / f"faers_ascii_{quarter}",
        DATA_DIR / f"faers_ascii_{quarter}_new",
    ]


def _is_quarter_extracted(quarter: str) -> bool:
    return any(p.exists() and p.is_dir() for p in _quarter_folder_candidates(quarter))


def _download_quarter_zip(quarter: str, force_download: bool, retries: int = 3) -> bool:
    if _is_quarter_extracted(quarter) and not force_download:
        _log(f"[SKIP] {quarter}: already extracted")
        return True

    zip_name = f"faers_ascii_{quarter}.zip"
    url = f"{FDA_EXPORT_BASE}/{zip_name}"
    raw_dir = DATA_DIR / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    zip_path = raw_dir / zip_name
    extract_dir = DATA_DIR / f"faers_ascii_{quarter}"

    if force_download and zip_path.exists():
        zip_path.unlink()

    if not zip_path.exists():
        ok = False
        for attempt in range(1, retries + 1):
            try:
                _log(f"[DOWN] {quarter}: {url} (attempt {attempt}/{retries})")
                resp = requests.get(url, timeout=60)
                if resp.status_code == 404:
                    _log(f"[MISS] {quarter}: file not found on FDA server")
                    return False
                resp.raise_for_status()
                zip_path.write_bytes(resp.content)
                ok = True
                break
            except Exception as exc:
                _log(f"[WARN] {quarter}: download failed ({exc})")
                time.sleep(2)
        if not ok:
            return False
    else:
        _log(f"[SKIP] {quarter}: zip already downloaded")

    if extract_dir.exists() and force_download:
        # Non-destructive policy: keep as-is and re-extract over top.
        _log(f"[INFO] {quarter}: re-extracting into existing directory")

    extract_dir.mkdir(parents=True, exist_ok=True)
    _log(f"[UNZIP] {quarter} -> {extract_dir}")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_dir)
    return True


def _select_folder_for_quarter(quarter: str) -> Path:
    candidates = [p for p in _quarter_folder_candidates(quarter) if p.exists()]
    if not candidates:
        raise FileNotFoundError(f"Missing extracted folder for {quarter}")
    candidates_sorted = sorted(
        candidates, key=lambda p: (0 if p.name.endswith("_new") else 1, p.name)
    )
    return candidates_sorted[0]


def _find_txt_for_table(quarter: str, folder: Path, prefix: str) -> Path:
    year, q = _quarter_key(quarter)
    yy = str(year)[-2:]
    base = f"{prefix}{yy}Q{q}"
    base_lo = base.lower()

    search_roots = [folder / "ascii", folder]
    names = [
        f"{base}.txt",
        f"{base}_new.txt",
        f"{base_lo}.txt",
        f"{base_lo}_new.txt",
    ]
    for root in search_roots:
        if not root.exists():
            continue
        for name in names:
            p = root / name
            if p.exists():
                return p
        for p in sorted(root.glob(f"{base}*.txt")):
            if p.exists():
                return p

    raise FileNotFoundError(
        f"Could not find {prefix} text file for {quarter} in {folder}"
    )


def _load_quarter_tables(quarter: str, folder: Path) -> dict[str, pd.DataFrame]:
    prefix_map = {
        "demo": "DEMO",
        "drug": "DRUG",
        "reac": "REAC",
        "outc": "OUTC",
        "rpsr": "RPSR",
        "ther": "THER",
        "indi": "INDI",
    }

    out: dict[str, pd.DataFrame] = {}
    for table, prefix in prefix_map.items():
        path = _find_txt_for_table(quarter, folder, prefix)
        _log(f"  loading {table} ({quarter}) from {path.name}")
        df = pd.read_csv(
            path,
            sep="$",
            dtype=str,
            encoding="latin-1",
            low_memory=False,
        )
        df.columns = [c.lower().strip() for c in df.columns]
        df["quarter"] = quarter
        out[table] = df
    return out


def _load_multi_quarter(quarters: Iterable[str]) -> dict[str, pd.DataFrame]:
    acc: dict[str, list[pd.DataFrame]] = {t: [] for t in TABLES}
    for q in quarters:
        folder = _select_folder_for_quarter(q)
        _log(f"Loading quarter {q} from {folder.name}")
        q_tables = _load_quarter_tables(q, folder)
        for t in TABLES:
            acc[t].append(q_tables[t])
    return {
        t: pd.concat(acc[t], ignore_index=True) if acc[t] else pd.DataFrame()
        for t in TABLES
    }


def _dedupe_and_filter(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    demo = tables["demo"].copy()
    before = len(demo)
    demo["caseversion"] = (
        pd.to_numeric(demo.get("caseversion", "0"), errors="coerce")
        .fillna(0)
        .astype(int)
    )
    demo = demo.sort_values("caseversion").drop_duplicates("caseid", keep="last")
    _log(f"demo dedup: {before:,} -> {len(demo):,} rows")

    valid_primaryids = set(demo["primaryid"].dropna().astype(str).tolist())
    tables["demo"] = demo

    for t in ("drug", "reac", "outc", "rpsr", "ther", "indi"):
        df = tables[t]
        b = len(df)
        df = df[df["primaryid"].astype(str).isin(valid_primaryids)].copy()
        if t in ("drug", "ther", "indi"):
            df = df.drop_duplicates()
        tables[t] = df
        _log(f"{t:>4s}: {b:,} -> {len(df):,} rows")

    return tables


def _parquet_files_exist(parquet_dir: Path) -> bool:
    return all((parquet_dir / f"{t}.parquet").exists() for t in TABLES)


def _build_parquet(
    mode_paths: ModePaths, mode: str, force_parquet: bool, quarters: list[str]
) -> None:
    parquet_dir = mode_paths.parquet_dir
    parquet_dir.mkdir(parents=True, exist_ok=True)

    if _parquet_files_exist(parquet_dir) and not force_parquet:
        _log(f"Parquet already present in {parquet_dir}. Skipping parquet build.")
        return

    _log(f"Building parquet tables for mode={mode} ...")
    tables = _load_multi_quarter(quarters)
    tables = _dedupe_and_filter(tables)

    for t in TABLES:
        out = parquet_dir / f"{t}.parquet"
        _log(f"Writing {out} ({len(tables[t]):,} rows)")
        tables[t].to_parquet(out, index=False)


def _required_cache_files(cache_dir: Path) -> list[Path]:
    names = [
        "demo_slim.parquet",
        "drug_records_slim.parquet",
        "reac_slim.parquet",
        "outc_slim.parquet",
        "indi_slim.parquet",
        "drug_summary.parquet",
        "reac_summary.parquet",
        "manufacturer_summary.parquet",
        "fact_drug_quarter.parquet",
        "fact_reac_quarter.parquet",
        "fact_manufacturer_quarter.parquet",
        "lookup_quarter_cases.parquet",
        "lookup_drug_cases.parquet",
        "lookup_reaction_cases.parquet",
        "lookup_manufacturer_cases.parquet",
        "manufacturer_name_lookup.parquet",
        "global_kpis.parquet",
    ]
    return [cache_dir / n for n in names]


def _cache_exists(cache_dir: Path) -> bool:
    req = _required_cache_files(cache_dir)
    return all(p.exists() for p in req)


def _build_cache(mode_paths: ModePaths, force_cache: bool) -> None:
    cache_dir = mode_paths.cache_dir
    cache_dir.mkdir(parents=True, exist_ok=True)
    if _cache_exists(cache_dir) and not force_cache:
        _log(f"Cache already present in {cache_dir}. Skipping cache build.")
        return

    env = os.environ.copy()
    env["FAERS_PARQUET_DIR"] = str(mode_paths.parquet_dir)
    env["FAERS_CACHE_DIR"] = str(mode_paths.cache_dir)
    _log("Building dashboard cache tables...")
    _run([sys.executable, "-m", "dashboard.precompute"], env=env)


def _launch_dashboard(mode_paths: ModePaths) -> None:
    env = os.environ.copy()
    env["FAERS_PARQUET_DIR"] = str(mode_paths.parquet_dir)
    env["FAERS_CACHE_DIR"] = str(mode_paths.cache_dir)
    app_path = DASHBOARD_DIR / "app.py"
    _log("Launching Streamlit dashboard...")
    _run([sys.executable, "-m", "streamlit", "run", str(app_path)], env=env)


def _compute_target_quarters(
    mode: str, start_q: str | None, end_q: str | None
) -> list[str]:
    if mode == "recent":
        quarters = _recent_quarters(n_years=2)
        if start_q or end_q:
            lo = start_q or quarters[0]
            hi = end_q or quarters[-1]
            quarters = [
                q
                for q in quarters
                if _quarter_key(lo) <= _quarter_key(q) <= _quarter_key(hi)
            ]
        return quarters

    start = start_q or "2012Q4"
    end = end_q
    return _all_quarters(start=start, end=end)


def main() -> None:
    args = _parse_args()
    mode_paths = _mode_paths(args.mode)

    _log(f"Project root: {PROJECT_ROOT}")
    _log(f"Mode: {args.mode}")
    _log(f"Parquet dir: {mode_paths.parquet_dir}")
    _log(f"Cache dir: {mode_paths.cache_dir}")

    _install_dependencies(args.skip_deps)

    quarters = _compute_target_quarters(args.mode, args.start_quarter, args.end_quarter)
    if not quarters:
        raise SystemExit("No quarters selected. Check --start-quarter / --end-quarter.")

    _log(f"Target quarters: {quarters[0]} -> {quarters[-1]} ({len(quarters)} quarters)")
    downloaded = []
    missing = []
    for q in quarters:
        ok = _download_quarter_zip(q, force_download=args.force_download)
        if ok:
            downloaded.append(q)
        else:
            missing.append(q)

    if not downloaded:
        raise SystemExit("No quarter data available to continue.")

    if missing:
        _log(
            f"Warning: {len(missing)} quarter(s) were unavailable and will be skipped: {', '.join(missing)}"
        )

    _build_parquet(
        mode_paths=mode_paths,
        mode=args.mode,
        force_parquet=args.force_parquet,
        quarters=downloaded,
    )
    _build_cache(mode_paths=mode_paths, force_cache=args.force_cache)

    _log("\nSetup complete.")
    _log("Run later with:")
    _log(
        f"  {sys.executable} utils/setup_dashboard.py --mode {args.mode} --run --skip-deps"
    )

    if args.run:
        _launch_dashboard(mode_paths)


if __name__ == "__main__":
    main()
