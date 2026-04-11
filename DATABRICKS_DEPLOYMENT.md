# Deploying On Databricks

This guide shows one practical way to use Databricks for the heavy FAERS processing and keep the Streamlit dashboard reproducible.

## Recommended Architecture

1. Use Spark on Databricks to ingest the raw FAERS ASCII quarterly extracts.
2. Write curated Parquet datasets to DBFS or a mounted cloud object store.
3. Build the dashboard cache files from those curated Parquet tables.
4. Run the Streamlit dashboard either:
   - on a Databricks app or serving environment if available in your workspace, or
   - on another host that can read the Parquet and cache paths from cloud storage.

The right split is:

- Spark for ingestion, cleaning, deduplication, and large joins
- Pandas/Streamlit for the analyst-facing UI and final interactive summaries

## What To Store

The dashboard expects seven Parquet tables:

- `demo.parquet`
- `drug.parquet`
- `reac.parquet`
- `outc.parquet`
- `rpsr.parquet`
- `ther.parquet`
- `indi.parquet`

It also benefits from five precomputed cache files:

- `prr_table.parquet`
- `drug_summary.parquet`
- `reac_summary.parquet`
- `quarterly_drug.parquet`
- `quarterly_reac.parquet`

## Step 1: Load Raw FAERS Data With Spark

Upload the FDA quarterly ZIPs to cloud storage or DBFS, then unpack them into a directory structure Databricks can read.

Example DBFS layout:

```text
dbfs:/mnt/faers/raw/faers_ascii_2025Q1/
dbfs:/mnt/faers/raw/faers_ascii_2025Q2/
dbfs:/mnt/faers/curated/parquet_recent/
dbfs:/mnt/faers/curated/parquet/
dbfs:/mnt/faers/cache/cache_recent/
dbfs:/mnt/faers/cache/cache_full/
```

In a Databricks notebook, use Spark to read the dollar-delimited text files:

```python
from pyspark.sql import functions as F

demo = (
    spark.read
    .option("header", True)
    .option("sep", "$")
    .option("encoding", "latin1")
    .csv("dbfs:/mnt/faers/raw/faers_ascii_2025Q2/ascii/DEMO25Q2.txt")
)

demo = demo.select([F.col(c).alias(c.lower().strip()) for c in demo.columns])
demo = demo.withColumn("quarter", F.lit("2025Q2"))
```

Repeat for `DRUG`, `REAC`, `OUTC`, `RPSR`, `THER`, and `INDI`, then union quarters together.

## Step 2: Deduplicate In Spark

The dashboard assumes FAERS deduplication by keeping the latest `caseversion` per `caseid`.

Example Spark pattern:

```python
from pyspark.sql import Window
from pyspark.sql import functions as F

w = Window.partitionBy("caseid").orderBy(F.col("caseversion").cast("int").desc())

demo_dedup = (
    demo_all
    .withColumn("rn", F.row_number().over(w))
    .filter(F.col("rn") == 1)
    .drop("rn")
)
```

Then filter the other tables to valid `primaryid` values from `demo_dedup`.

## Step 3: Write Curated Parquet

Write the deduplicated outputs to DBFS or mounted object storage:

```python
demo_dedup.write.mode("overwrite").parquet("dbfs:/mnt/faers/curated/parquet/demo.parquet")
drug_curated.write.mode("overwrite").parquet("dbfs:/mnt/faers/curated/parquet/drug.parquet")
reac_curated.write.mode("overwrite").parquet("dbfs:/mnt/faers/curated/parquet/reac.parquet")
```

If you want a smaller testing dataset, write the last two years to `parquet_recent/` and the full dataset to `parquet/`.

## Step 4: Build Dashboard Cache Files

The dashboard cache builder is still a Python job, but it can run against Databricks-backed storage by setting environment variables.

Example:

```bash
FAERS_PARQUET_DIR=/dbfs/mnt/faers/curated/parquet_recent \
FAERS_CACHE_DIR=/dbfs/mnt/faers/cache/cache_recent \
python3 dashboard/precompute.py
```

For full data:

```bash
FAERS_PARQUET_DIR=/dbfs/mnt/faers/curated/parquet \
FAERS_CACHE_DIR=/dbfs/mnt/faers/cache/cache_full \
python3 dashboard/precompute.py
```

You can run this as:

- a Databricks job on a small single-node cluster
- a notebook task
- or a downstream CI/CD step on a machine that has access to the mounted paths

## Step 5: Run The Dashboard

Run the dashboard with the same paths:

```bash
FAERS_PARQUET_DIR=/dbfs/mnt/faers/curated/parquet_recent \
FAERS_CACHE_DIR=/dbfs/mnt/faers/cache/cache_recent \
streamlit run dashboard/app.py
```

Or use the helper script:

```bash
python3 utils/run_dashboard.py --mode recent
```

If you are not running on the Databricks driver itself, point `FAERS_PARQUET_DIR` and `FAERS_CACHE_DIR` at the mounted cloud storage path visible to your host.

## Best Databricks Setup For This Repo

For a class project, the most practical option is:

1. Databricks notebook/job does ingestion and dedup with Spark.
2. Curated Parquet lands in DBFS or mounted cloud storage.
3. `dashboard/precompute.py` runs against that curated output.
4. Streamlit app runs either locally or on a lightweight VM/container against the generated files.

This gives you a credible “big data pipeline on Spark” story without forcing the dashboard itself to depend on a live Spark session.

## Suggested Notebook Flow

Create a notebook with sections like:

1. `Parameters`
   - `mode = "recent"` or `mode = "full"`
   - source and target paths
2. `Read Raw FAERS`
3. `Normalize Columns`
4. `Deduplicate DEMO`
5. `Filter Related Tables`
6. `Write Curated Parquet`
7. `Validation Counts`

Useful validation checks:

- row counts by table
- distinct `caseid`
- distinct `primaryid`
- min and max quarter
- null rate for key columns like `drugname`, `pt`, and `outc_cod`

## Operational Notes

- Keep recent and full outputs separate. Do not reuse the same cache directory for both.
- Precompute cache files after every major dataset refresh.
- If the full `prr_table.parquet` gets too large, reduce the `TOP_DRUGS` setting in [dashboard/precompute.py](/Users/hayden/coderepos_mac_mini/bigdataproject/dashboard/precompute.py) or materialize more summaries in Spark first.
- If you want a stricter Spark story, you can port parts of `dashboard/precompute.py` into Spark SQL or PySpark and write the same output schema.

## Minimal Deployment Checklist

- Raw FAERS data available in DBFS or mounted cloud storage
- Spark notebook/job produces curated Parquet tables
- Cache files built into a matching cache directory
- `FAERS_PARQUET_DIR` points to curated Parquet
- `FAERS_CACHE_DIR` points to matching cache
- Streamlit process can read both locations
