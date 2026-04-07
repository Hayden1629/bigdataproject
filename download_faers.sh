#!/usr/bin/env bash
# download_faers.sh
#
# Downloads all FAERS ASCII quarterly data extracts from FDA.
# Files are saved to data/raw/ and extracted to data/faers_ascii_{year}Q{quarter}/
#
# Usage:
#   ./download_faers.sh                  # download all quarters (2012Q4 - 2025Q4)
#   ./download_faers.sh 2020Q1 2025Q4    # download a specific range
#
# Requires: curl, unzip

set -euo pipefail

BASE_URL="https://fis.fda.gov/content/Exports"
DATA_DIR="$(dirname "$0")/data"
RAW_DIR="$DATA_DIR/raw"

mkdir -p "$RAW_DIR"

# Build list of all quarters from 2012Q4 through 2025Q4
# FAERS started with 2012Q4 (first extract)
all_quarters() {
    local start_year=2012
    local end_year=2025

    for year in $(seq $start_year $end_year); do
        for q in 1 2 3 4; do
            # FAERS starts at 2012Q4
            if [ "$year" -eq 2012 ] && [ "$q" -lt 4 ]; then
                continue
            fi
            echo "${year}Q${q}"
        done
    done
}

# Parse optional start/end args
START_QUARTER="${1:-2012Q4}"
END_QUARTER="${2:-2025Q4}"

# Filter quarters to the requested range
quarters_in_range() {
    local in_range=0
    while IFS= read -r q; do
        if [ "$q" = "$START_QUARTER" ]; then
            in_range=1
        fi
        if [ "$in_range" -eq 1 ]; then
            echo "$q"
        fi
        if [ "$q" = "$END_QUARTER" ]; then
            break
        fi
    done
}

quarters=$(all_quarters | quarters_in_range)

echo "Downloading FAERS ASCII extracts: $START_QUARTER through $END_QUARTER"
echo "Destination: $DATA_DIR"
echo ""

for quarter in $quarters; do
    year="${quarter%Q*}"         # e.g. 2025
    yy="${year: -2}"             # e.g. 25
    q="${quarter#*Q}"            # e.g. 4

    zip_name="faers_ascii_${year}Q${q}.zip"
    url="${BASE_URL}/${zip_name}"
    dest_zip="$RAW_DIR/${zip_name}"
    extract_dir="$DATA_DIR/faers_ascii_${year}Q${q}"

    if [ -d "$extract_dir" ]; then
        echo "[SKIP] $quarter — already extracted at $extract_dir"
        continue
    fi

    if [ -f "$dest_zip" ]; then
        echo "[SKIP] $quarter — zip already downloaded, extracting..."
    else
        echo "[DOWN] $quarter — $url"
        curl -fsSL --retry 3 --retry-delay 5 \
             -o "$dest_zip" \
             "$url" \
        || { echo "  WARNING: failed to download $zip_name (quarter may not exist yet)" ; rm -f "$dest_zip"; continue; }
    fi

    echo "[UNZIP] $quarter -> $extract_dir"
    mkdir -p "$extract_dir"
    unzip -q "$dest_zip" -d "$extract_dir"
    echo "[DONE]  $quarter"
done

echo ""
echo "All done. Data is in: $DATA_DIR"
