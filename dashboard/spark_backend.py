from __future__ import annotations

import os
import threading
import time
from typing import Any

import pandas as pd

from dashboard.logging_utils import get_logger


logger = get_logger(__name__)

_local = threading.local()


def is_enabled() -> bool:
    raw = os.environ.get("FAERS_USE_SPARK_SQL", "0").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _get_connection():
    conn = getattr(_local, "conn", None)
    if conn is not None:
        try:
            conn.cursor().execute("SELECT 1")
            return conn
        except Exception:
            try:
                conn.close()
            except Exception:
                pass
            _local.conn = None

    from databricks import sql as dbsql
    from databricks.sdk import WorkspaceClient

    w = WorkspaceClient()
    host = (w.config.host or "").rstrip("/")
    if host.startswith("https://"):
        host = host[len("https://"):]

    warehouse_id = os.environ.get("DATABRICKS_WAREHOUSE_ID", "").strip()
    http_path = f"/sql/1.0/warehouses/{warehouse_id}" if warehouse_id else ""

    logger.info("Connecting to %s warehouse=%s", host, warehouse_id)

    # Get token from SDK (handles OAuth/PAT/service principal automatically)
    headers = w.config.authenticate()
    token = headers.get("Authorization", "").replace("Bearer ", "")

    conn = dbsql.connect(
        server_hostname=host,
        http_path=http_path,
        access_token=token,
        use_cloud_fetch=False,
    )
    _local.conn = conn
    return conn


def _sql_str(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _q_list(values: list[str] | tuple[str, ...]) -> str:
    return ", ".join(_sql_str(v) for v in values if str(v).strip())


def _table(name: str) -> str:
    catalog = os.environ.get("FAERS_SPARK_CATALOG", "").strip()
    schema = os.environ.get("FAERS_SPARK_SCHEMA", "").strip()
    database = os.environ.get("FAERS_SPARK_DATABASE", "").strip()
    if catalog and schema:
        return f"{catalog}.{schema}.{name}"
    if database:
        return f"{database}.{name}"
    return name


def _run_sql(sql: str) -> pd.DataFrame:
    t0 = time.perf_counter()
    conn = _get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(sql)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        out = pd.DataFrame(rows, columns=columns)
    finally:
        cursor.close()
    logger.info(
        "sql completed (rows=%s, %.3fs)", len(out), time.perf_counter() - t0
    )
    return out


def _quarter_filter(alias: str, quarters: tuple[str, ...] | list[str] | None) -> str:
    q = [str(x) for x in (quarters or []) if str(x).strip()]
    if not q:
        return ""
    return f" AND {alias}.year_q IN ({_q_list(q)})"


def _role_filter(alias: str, role_filter: str) -> str:
    role = (role_filter or "all").strip().upper()
    if role in {"", "ALL"}:
        return ""
    return f" AND UPPER({alias}.role_cod) = {_sql_str(role)}"


def _ids_sql_for_drug(
    matched_names: tuple[str, ...], quarters: tuple[str, ...], role_filter: str
) -> str:
    where = "WHERE 1=1"
    if matched_names:
        where += f" AND d.drugname IN ({_q_list(list(matched_names))})"
    where += _quarter_filter("d", quarters)
    where += _role_filter("d", role_filter)
    return f"SELECT DISTINCT CAST(d.primaryid AS STRING) AS primaryid FROM {_table('drug_records_slim')} d {where}"


def _ids_sql_for_reaction(
    terms: tuple[str, ...], quarters: tuple[str, ...], role_filter: str
) -> str:
    if not terms:
        return "SELECT CAST(NULL AS STRING) AS primaryid WHERE 1=0"
    reac_where = f"WHERE r.pt IN ({_q_list(list(terms))})" + _quarter_filter(
        "r", quarters
    )
    if (role_filter or "all").lower() == "all":
        return (
            "SELECT DISTINCT CAST(r.primaryid AS STRING) AS primaryid "
            f"FROM {_table('reac_slim')} r {reac_where}"
        )
    return (
        "SELECT DISTINCT CAST(r.primaryid AS STRING) AS primaryid "
        f"FROM {_table('reac_slim')} r "
        f"INNER JOIN {_table('drug_records_slim')} d ON CAST(r.primaryid AS STRING)=CAST(d.primaryid AS STRING) "
        f"{reac_where}{_role_filter('d', role_filter)}"
    )


def _ids_sql_for_manufacturer(
    canonical_names: tuple[str, ...], quarters: tuple[str, ...], role_filter: str
) -> str:
    if not canonical_names:
        return "SELECT CAST(NULL AS STRING) AS primaryid WHERE 1=0"
    base_where = (
        f"WHERE m.canonical_mfr IN ({_q_list(list(canonical_names))})"
        + _quarter_filter("m", quarters)
    )
    if (role_filter or "all").lower() == "all":
        return (
            "SELECT DISTINCT CAST(m.primaryid AS STRING) AS primaryid "
            f"FROM {_table('demo_slim')} m {base_where}"
        )
    return (
        "SELECT DISTINCT CAST(m.primaryid AS STRING) AS primaryid "
        f"FROM {_table('demo_slim')} m "
        f"INNER JOIN {_table('drug_records_slim')} d ON CAST(m.primaryid AS STRING)=CAST(d.primaryid AS STRING) "
        f"{base_where}{_role_filter('d', role_filter)}"
    )


def _ids_count(ids_sql: str) -> int:
    q = f"SELECT COUNT(1) AS n FROM ({ids_sql}) x"
    out = _run_sql(q)
    if out.empty:
        return 0
    return int(out.iloc[0]["n"])


def _ids_set(ids_sql: str) -> set[str]:
    out = _run_sql(f"SELECT primaryid FROM ({ids_sql}) x")
    if out.empty:
        return set()
    return set(out["primaryid"].astype(str).tolist())


def _top_counts_by_ids(
    table: str,
    col: str,
    top_n: int,
    ids_sql: str,
    label_map: dict[str, str] | None = None,
) -> pd.DataFrame:
    sql = f"""
        SELECT
          CAST(t.{col} AS STRING) AS {col},
          COUNT(DISTINCT CAST(t.primaryid AS STRING)) AS n_cases
        FROM {_table(table)} t
        INNER JOIN ({ids_sql}) ids ON CAST(t.primaryid AS STRING)=ids.primaryid
        WHERE t.{col} IS NOT NULL AND TRIM(CAST(t.{col} AS STRING)) <> ''
        GROUP BY CAST(t.{col} AS STRING)
        ORDER BY n_cases DESC
        LIMIT {int(top_n)}
    """
    out = _run_sql(sql)
    if label_map is not None and not out.empty:
        out[col] = out[col].map(lambda v: label_map.get(str(v), str(v)))
    return out


def _kpi_from_ids(ids_sql: str) -> dict[str, Any]:
    out = _run_sql(
        f"""
        WITH ids AS ({ids_sql}),
        outc AS (
          SELECT UPPER(CAST(o.outc_cod AS STRING)) AS outc_cod, CAST(o.primaryid AS STRING) AS primaryid
          FROM {_table("outc_slim")} o
          INNER JOIN ids i ON CAST(o.primaryid AS STRING)=i.primaryid
        )
        SELECT
          (SELECT COUNT(1) FROM ids) AS cases,
          COUNT(DISTINCT CASE WHEN outc_cod='DE' THEN primaryid END) AS deaths,
          COUNT(DISTINCT CASE WHEN outc_cod='HO' THEN primaryid END) AS hospitalisations,
          COUNT(DISTINCT CASE WHEN outc_cod='LT' THEN primaryid END) AS life_threatening,
          COUNT(DISTINCT primaryid) AS serious
        FROM outc
        """
    )
    if out.empty:
        return {
            "cases": 0,
            "deaths": 0,
            "death_pct": 0.0,
            "hospitalisations": 0,
            "life_threatening": 0,
            "serious": 0,
            "serious_pct": 0.0,
        }
    row = out.iloc[0]
    cases = int(row.get("cases", 0) or 0)
    deaths = int(row.get("deaths", 0) or 0)
    hosps = int(row.get("hospitalisations", 0) or 0)
    life = int(row.get("life_threatening", 0) or 0)
    serious = int(row.get("serious", 0) or 0)
    return {
        "cases": cases,
        "deaths": deaths,
        "death_pct": (deaths / cases * 100.0) if cases else 0.0,
        "hospitalisations": hosps,
        "life_threatening": life,
        "serious": serious,
        "serious_pct": (serious / cases * 100.0) if cases else 0.0,
    }


def _build_case_table(ids_sql: str, include_lit_ref: bool = False, limit: int = 1000) -> pd.DataFrame:
    sql = f"""
        WITH ids AS ({ids_sql}),
        demo AS (
          SELECT
            CAST(primaryid AS STRING) AS primaryid,
            FIRST(CAST(event_dt AS STRING), true) AS event_dt,
            FIRST(CAST(occr_country AS STRING), true) AS country,
            FIRST(CAST(mfr_sndr AS STRING), true) AS mfr_sndr,
            FIRST(CAST(canonical_mfr AS STRING), true) AS canonical_mfr,
            FIRST(CAST(lit_ref AS STRING), true) AS lit_ref
          FROM {_table("demo_slim")}
          WHERE CAST(primaryid AS STRING) IN (SELECT primaryid FROM ids)
          GROUP BY CAST(primaryid AS STRING)
        ),
        drug AS (
          SELECT
            CAST(primaryid AS STRING) AS primaryid,
            FIRST(CAST(role_cod AS STRING), true) AS role,
            FIRST(CAST(route AS STRING), true) AS route,
            FIRST(CAST(dose_amt AS STRING), true) AS dose_amt,
            FIRST(CAST(dose_unit AS STRING), true) AS dose_unit,
            FIRST(CAST(dose_form AS STRING), true) AS dose_form,
            FIRST(CAST(dose_freq AS STRING), true) AS dose_freq,
            FIRST(CAST(mfr_sndr AS STRING), true) AS drug_mfr,
            FIRST(CAST(prod_ai AS STRING), true) AS active_ingredient
          FROM {_table("drug_records_slim")}
          WHERE CAST(primaryid AS STRING) IN (SELECT primaryid FROM ids)
          GROUP BY CAST(primaryid AS STRING)
        ),
        reac AS (
          SELECT CAST(primaryid AS STRING) AS primaryid, FIRST(CAST(pt AS STRING), true) AS top_reaction
          FROM {_table("reac_slim")}
          WHERE CAST(primaryid AS STRING) IN (SELECT primaryid FROM ids)
          GROUP BY CAST(primaryid AS STRING)
        ),
        indi AS (
          SELECT CAST(primaryid AS STRING) AS primaryid, FIRST(CAST(indi_pt AS STRING), true) AS top_indication
          FROM {_table("indi_slim")}
          WHERE CAST(primaryid AS STRING) IN (SELECT primaryid FROM ids)
          GROUP BY CAST(primaryid AS STRING)
        ),
        outc AS (
          SELECT
            CAST(primaryid AS STRING) AS primaryid,
            CONCAT_WS(', ', SORT_ARRAY(COLLECT_SET(CAST(outc_cod AS STRING)))) AS outcomes
          FROM {_table("outc_slim")}
          WHERE CAST(primaryid AS STRING) IN (SELECT primaryid FROM ids)
          GROUP BY CAST(primaryid AS STRING)
        )
        SELECT
          d.primaryid,
          COALESCE(dm.event_dt, '') AS event_dt,
          COALESCE(dm.country, '') AS country,
          COALESCE(d.role, '') AS role,
          COALESCE(d.route, '') AS route,
          TRIM(CONCAT(COALESCE(d.dose_amt, ''), ' ', COALESCE(d.dose_unit, ''))) AS dose,
          COALESCE(d.dose_form, '') AS dose_form,
          COALESCE(d.dose_freq, '') AS dose_freq,
          COALESCE(NULLIF(dm.mfr_sndr, ''), d.drug_mfr, '') AS manufacturer,
          COALESCE(dm.canonical_mfr, '') AS canonical_mfr,
          COALESCE(d.active_ingredient, '') AS active_ingredient,
          COALESCE(r.top_reaction, '') AS top_reaction,
          COALESCE(o.outcomes, '') AS outcomes,
          COALESCE(i.top_indication, '') AS top_indication,
          COALESCE(dm.lit_ref, '') AS lit_ref
        FROM drug d
        LEFT JOIN demo dm ON d.primaryid = dm.primaryid
        LEFT JOIN reac r ON d.primaryid = r.primaryid
        LEFT JOIN indi i ON d.primaryid = i.primaryid
        LEFT JOIN outc o ON d.primaryid = o.primaryid
        LIMIT {int(limit)}
    """
    out = _run_sql(sql)
    if not include_lit_ref and "lit_ref" in out.columns:
        out = out.drop(columns=["lit_ref"])
    return out


def warm_all_tables() -> None:
    names = [
        "demo_slim",
        "drug_records_slim",
        "reac_slim",
        "outc_slim",
        "rpsr_slim",
        "indi_slim",
        "drug_name_lookup",
        "manufacturer_name_lookup",
        "fact_drug_quarter",
        "fact_reac_quarter",
    ]
    t0 = time.perf_counter()
    for name in names:
        full = _table(name)
        try:
            _run_sql(f"SELECT 1 FROM {full} LIMIT 1")
        except Exception:
            logger.info("warm skip missing table: %s", full)
    logger.info("Table warm completed in %.3fs", time.perf_counter() - t0)


def get_quarters() -> list[str]:
    out = _run_sql(
        f"SELECT DISTINCT CAST(year_q AS STRING) AS year_q FROM {_table('demo_slim')} WHERE TRIM(CAST(year_q AS STRING)) <> '' ORDER BY year_q"
    )
    return out["year_q"].astype(str).tolist() if not out.empty else []


def get_dataset_profile() -> dict[str, Any]:
    quarters = get_quarters()
    out = _run_sql(
        f"SELECT COUNT(DISTINCT CAST(primaryid AS STRING)) AS cases FROM {_table('demo_slim')}"
    )
    cases = int(out.iloc[0]["cases"]) if not out.empty else 0
    mode = os.environ.get("FAERS_DATA_MODE", "spark")
    return {
        "mode": mode,
        "cases": cases,
        "quarter_min": quarters[0] if quarters else "-",
        "quarter_max": quarters[-1] if quarters else "-",
        "quarters": quarters,
    }


def load_drug_name_lookup() -> pd.DataFrame:
    try:
        return _run_sql(
            f"SELECT drugname, drugname_norm, prod_ai, prod_ai_norm FROM {_table('drug_name_lookup')}"
        )
    except Exception:
        return _run_sql(
            f"SELECT DISTINCT CAST(drugname AS STRING) AS drugname, LOWER(TRIM(CAST(drugname AS STRING))) AS drugname_norm, CAST(prod_ai AS STRING) AS prod_ai, LOWER(TRIM(CAST(prod_ai AS STRING))) AS prod_ai_norm FROM {_table('drug_records_slim')}"
        )


def load_manufacturer_lookup() -> pd.DataFrame:
    try:
        return _run_sql(
            f"SELECT mfr_sndr, canonical_mfr, n_cases FROM {_table('manufacturer_name_lookup')}"
        )
    except Exception:
        return _run_sql(
            f"SELECT CAST(mfr_sndr AS STRING) AS mfr_sndr, CAST(canonical_mfr AS STRING) AS canonical_mfr, COUNT(DISTINCT CAST(primaryid AS STRING)) AS n_cases FROM {_table('demo_slim')} WHERE TRIM(CAST(canonical_mfr AS STRING)) <> '' GROUP BY CAST(mfr_sndr AS STRING), CAST(canonical_mfr AS STRING) ORDER BY n_cases DESC"
        )


def get_all_reaction_terms() -> list[str]:
    out = _run_sql(
        f"SELECT DISTINCT CAST(pt AS STRING) AS pt FROM {_table('reac_slim')} WHERE TRIM(CAST(pt AS STRING)) <> '' ORDER BY pt"
    )
    return out["pt"].astype(str).tolist() if not out.empty else []


def load_drug_summary() -> pd.DataFrame:
    try:
        return _run_sql(f"SELECT drugname, n_cases FROM {_table('drug_summary')}")
    except Exception:
        return _run_sql(
            f"SELECT CAST(drugname AS STRING) AS drugname, COUNT(DISTINCT CAST(primaryid AS STRING)) AS n_cases FROM {_table('drug_records_slim')} WHERE TRIM(CAST(drugname AS STRING)) <> '' GROUP BY CAST(drugname AS STRING) ORDER BY n_cases DESC"
        )


def load_reac_summary() -> pd.DataFrame:
    try:
        return _run_sql(f"SELECT pt, n_cases FROM {_table('reac_summary')}")
    except Exception:
        return _run_sql(
            f"SELECT CAST(pt AS STRING) AS pt, COUNT(DISTINCT CAST(primaryid AS STRING)) AS n_cases FROM {_table('reac_slim')} WHERE TRIM(CAST(pt AS STRING)) <> '' GROUP BY CAST(pt AS STRING) ORDER BY n_cases DESC"
        )


def load_manufacturer_summary() -> pd.DataFrame:
    try:
        return _run_sql(
            f"SELECT canonical_mfr, n_cases FROM {_table('manufacturer_summary')}"
        )
    except Exception:
        return _run_sql(
            f"SELECT CAST(canonical_mfr AS STRING) AS canonical_mfr, COUNT(DISTINCT CAST(primaryid AS STRING)) AS n_cases FROM {_table('demo_slim')} WHERE TRIM(CAST(canonical_mfr AS STRING)) <> '' GROUP BY CAST(canonical_mfr AS STRING) ORDER BY n_cases DESC"
        )


def global_kpis(quarters: tuple[str, ...], role_filter: str) -> dict[str, Any]:
    ids_sql = (
        f"SELECT DISTINCT CAST(d.primaryid AS STRING) AS primaryid FROM {_table('demo_slim')} d "
        f"WHERE 1=1{_quarter_filter('d', quarters)}"
    )
    out = _run_sql(
        f"""
        WITH ids AS ({ids_sql}),
        drug AS (
          SELECT CAST(dr.primaryid AS STRING) AS primaryid, CAST(dr.drugname AS STRING) AS drugname
          FROM {_table("drug_records_slim")} dr
          INNER JOIN ids i ON CAST(dr.primaryid AS STRING)=i.primaryid
          WHERE 1=1{_role_filter("dr", role_filter)}
        ),
        reac AS (
          SELECT CAST(r.primaryid AS STRING) AS primaryid, CAST(r.pt AS STRING) AS pt
          FROM {_table("reac_slim")} r
          INNER JOIN ids i ON CAST(r.primaryid AS STRING)=i.primaryid
        ),
        outc AS (
          SELECT CAST(o.primaryid AS STRING) AS primaryid, UPPER(CAST(o.outc_cod AS STRING)) AS outc_cod
          FROM {_table("outc_slim")} o
          INNER JOIN ids i ON CAST(o.primaryid AS STRING)=i.primaryid
        )
        SELECT
          (SELECT COUNT(1) FROM ids) AS cases,
          COUNT(DISTINCT CASE WHEN outc_cod='DE' THEN primaryid END) AS deaths,
          COUNT(DISTINCT CASE WHEN outc_cod='HO' THEN primaryid END) AS hospitalisations,
          COUNT(DISTINCT CASE WHEN outc_cod='LT' THEN primaryid END) AS life_threatening,
          COUNT(DISTINCT outc.primaryid) AS serious,
          (SELECT COUNT(DISTINCT drugname) FROM drug WHERE TRIM(drugname) <> '') AS unique_drugs,
          (SELECT COUNT(DISTINCT pt) FROM reac WHERE TRIM(pt) <> '') AS unique_reactions
        FROM outc
        """
    )
    if out.empty:
        return {
            "cases": 0,
            "deaths": 0,
            "death_pct": 0.0,
            "hospitalisations": 0,
            "life_threatening": 0,
            "serious": 0,
            "serious_pct": 0.0,
            "unique_drugs": 0,
            "unique_reactions": 0,
        }
    row = out.iloc[0]
    cases = int(row.get("cases", 0) or 0)
    deaths = int(row.get("deaths", 0) or 0)
    serious = int(row.get("serious", 0) or 0)
    return {
        "cases": cases,
        "deaths": deaths,
        "death_pct": (deaths / cases * 100.0) if cases else 0.0,
        "hospitalisations": int(row.get("hospitalisations", 0) or 0),
        "life_threatening": int(row.get("life_threatening", 0) or 0),
        "serious": serious,
        "serious_pct": (serious / cases * 100.0) if cases else 0.0,
        "unique_drugs": int(row.get("unique_drugs", 0) or 0),
        "unique_reactions": int(row.get("unique_reactions", 0) or 0),
    }


def global_quarterly_trend(quarters: tuple[str, ...], role_filter: str) -> pd.DataFrame:
    ids_sql = f"SELECT DISTINCT CAST(primaryid AS STRING) AS primaryid FROM {_table('demo_slim')} WHERE 1=1{_quarter_filter('demo_slim', quarters)}"
    if (role_filter or "all").lower() == "all":
        valid_ids_sql = ids_sql
    else:
        valid_ids_sql = (
            "SELECT DISTINCT i.primaryid FROM ("
            + ids_sql
            + ") i INNER JOIN "
            + _table("drug_records_slim")
            + " d ON i.primaryid=CAST(d.primaryid AS STRING) WHERE 1=1"
            + _role_filter("d", role_filter)
        )
    return _run_sql(
        f"""
        SELECT CAST(d.year_q AS STRING) AS year_q, COUNT(DISTINCT CAST(d.primaryid AS STRING)) AS n_cases
        FROM {_table("demo_slim")} d
        INNER JOIN ({valid_ids_sql}) ids ON CAST(d.primaryid AS STRING)=ids.primaryid
        GROUP BY CAST(d.year_q AS STRING)
        ORDER BY year_q
        """
    )


def _trend_delta(table: str, key_col: str, top_n: int) -> pd.DataFrame:
    qdf = _run_sql(
        f"SELECT DISTINCT CAST(year_q AS STRING) AS year_q FROM {_table(table)} WHERE TRIM(CAST(year_q AS STRING)) <> '' ORDER BY year_q"
    )
    if qdf.empty or len(qdf) < 2:
        return pd.DataFrame(columns=[key_col, "delta"])
    prev_q = str(qdf.iloc[-2]["year_q"])
    curr_q = str(qdf.iloc[-1]["year_q"])
    sql = f"""
        WITH a AS (
          SELECT CAST({key_col} AS STRING) AS k, SUM(CAST(n_cases AS BIGINT)) AS n
          FROM {_table(table)}
          WHERE CAST(year_q AS STRING) = {_sql_str(prev_q)}
          GROUP BY CAST({key_col} AS STRING)
        ),
        b AS (
          SELECT CAST({key_col} AS STRING) AS k, SUM(CAST(n_cases AS BIGINT)) AS n
          FROM {_table(table)}
          WHERE CAST(year_q AS STRING) = {_sql_str(curr_q)}
          GROUP BY CAST({key_col} AS STRING)
        )
        SELECT COALESCE(b.k, a.k) AS {key_col}, COALESCE(b.n, 0) - COALESCE(a.n, 0) AS delta
        FROM a FULL OUTER JOIN b ON a.k = b.k
        ORDER BY delta DESC
        LIMIT {int(top_n)}
    """
    return _run_sql(sql)


def trending_drugs(top_n: int = 10) -> pd.DataFrame:
    return _trend_delta("fact_drug_quarter", "drugname", top_n)


def trending_reactions(top_n: int = 10) -> pd.DataFrame:
    return _trend_delta("fact_reac_quarter", "pt", top_n)


def drug_query_bundle(
    matched_names: tuple[str, ...],
    top_n: int,
    role_filter: str,
    quarters: tuple[str, ...],
) -> dict[str, Any]:
    from concurrent.futures import ThreadPoolExecutor

    ids_sql = _ids_sql_for_drug(matched_names, quarters, role_filter)
    ids = _ids_set(ids_sql)
    if not ids:
        return {
            "primaryids": set(),
            "kpi": _kpi_from_ids(ids_sql),
            "recent": pd.DataFrame(),
            "top_reactions": pd.DataFrame(),
            "outcomes": pd.DataFrame(),
            "trend": pd.DataFrame(),
            "demographics": {},
            "countries": pd.DataFrame(),
            "indications": pd.DataFrame(),
            "concomitants": pd.DataFrame(),
        }

    with ThreadPoolExecutor(max_workers=12) as pool:
        f_kpi = pool.submit(_kpi_from_ids, ids_sql)
        f_recent = pool.submit(
            _run_sql,
            f"""
            SELECT CAST(d.primaryid AS STRING) AS primaryid, CAST(d.role_cod AS STRING) AS role_cod,
                   CAST(d.drugname AS STRING) AS drugname, CAST(d.prod_ai AS STRING) AS prod_ai,
                   CAST(d.route AS STRING) AS route, CAST(d.dose_amt AS STRING) AS dose_amt,
                   CAST(d.dose_unit AS STRING) AS dose_unit, CAST(d.dose_form AS STRING) AS dose_form,
                   CAST(d.dose_freq AS STRING) AS dose_freq
            FROM {_table("drug_records_slim")} d
            INNER JOIN ({ids_sql}) ids ON CAST(d.primaryid AS STRING)=ids.primaryid
            LIMIT 100
            """,
        )
        f_trend = pool.submit(
            _run_sql,
            f"SELECT CAST(d.year_q AS STRING) AS year_q, COUNT(DISTINCT CAST(d.primaryid AS STRING)) AS n_cases FROM {_table('demo_slim')} d INNER JOIN ({ids_sql}) ids ON CAST(d.primaryid AS STRING)=ids.primaryid GROUP BY CAST(d.year_q AS STRING) ORDER BY year_q",
        )
        f_sex = pool.submit(
            _run_sql,
            f"SELECT CAST(d.sex AS STRING) AS sex, COUNT(DISTINCT CAST(d.primaryid AS STRING)) AS n_cases FROM {_table('demo_slim')} d INNER JOIN ({ids_sql}) ids ON CAST(d.primaryid AS STRING)=ids.primaryid GROUP BY CAST(d.sex AS STRING) ORDER BY n_cases DESC",
        )
        f_age = pool.submit(
            _run_sql,
            f"""
            SELECT age_group, COUNT(DISTINCT primaryid) AS n_cases
            FROM (
              SELECT CAST(d.primaryid AS STRING) AS primaryid,
                     CASE
                       WHEN CAST(d.age AS DOUBLE) BETWEEN 0 AND 17 THEN '0-17'
                       WHEN CAST(d.age AS DOUBLE) > 17 AND CAST(d.age AS DOUBLE) <= 35 THEN '18-35'
                       WHEN CAST(d.age AS DOUBLE) > 35 AND CAST(d.age AS DOUBLE) <= 50 THEN '36-50'
                       WHEN CAST(d.age AS DOUBLE) > 50 AND CAST(d.age AS DOUBLE) <= 65 THEN '51-65'
                       WHEN CAST(d.age AS DOUBLE) > 65 THEN '66+'
                       ELSE NULL
                     END AS age_group
              FROM {_table("demo_slim")} d
              INNER JOIN ({ids_sql}) ids ON CAST(d.primaryid AS STRING)=ids.primaryid
            ) x
            WHERE age_group IS NOT NULL
            GROUP BY age_group
            """,
        )
        f_reporter = pool.submit(_top_counts_by_ids, "rpsr_slim", "rpsr_cod", top_n, ids_sql)
        f_countries = pool.submit(_top_counts_by_ids, "demo_slim", "occr_country", top_n, ids_sql)
        f_reactions = pool.submit(_top_counts_by_ids, "reac_slim", "pt", top_n, ids_sql)
        f_outcomes = pool.submit(_top_counts_by_ids, "outc_slim", "outc_cod", top_n, ids_sql)
        f_indications = pool.submit(_top_counts_by_ids, "indi_slim", "indi_pt", top_n, ids_sql)
        f_concomitants = pool.submit(_top_counts_by_ids, "drug_records_slim", "drugname", top_n + 5, ids_sql)

        concomitants = f_concomitants.result()
        if not concomitants.empty and matched_names:
            concomitants = concomitants[
                ~concomitants["drugname"].isin([str(x) for x in matched_names])
            ].head(int(top_n))

        return {
            "primaryids": ids,
            "kpi": f_kpi.result(),
            "recent": f_recent.result(),
            "top_reactions": f_reactions.result(),
            "outcomes": f_outcomes.result(),
            "trend": f_trend.result(),
            "demographics": {
                "sex": f_sex.result(),
                "age_group": f_age.result(),
                "reporter": f_reporter.result(),
            },
            "countries": f_countries.result(),
            "indications": f_indications.result(),
            "concomitants": concomitants,
        }


def _ids_sql_from_primaryids(primaryids: tuple[str, ...]) -> str:
    if not primaryids:
        return "SELECT CAST(NULL AS STRING) AS primaryid WHERE 1=0"
    return (
        "SELECT DISTINCT CAST(primaryid AS STRING) AS primaryid FROM "
        + _table("drug_records_slim")
        + f" WHERE CAST(primaryid AS STRING) IN ({_q_list(list(primaryids))})"
    )


def drug_provider_bundle(
    primaryids: tuple[str, ...],
    top_n: int,
    role_filter: str,
    quarters: tuple[str, ...],
    matched_names: tuple[str, ...] = (),
) -> dict[str, Any]:
    from concurrent.futures import ThreadPoolExecutor

    ids_sql = (
        _ids_sql_for_drug(matched_names, quarters, role_filter)
        if matched_names
        else _ids_sql_from_primaryids(primaryids)
    )
    if _ids_count(ids_sql) == 0:
        return {
            "ingredients": pd.DataFrame(),
            "role_counts": pd.DataFrame(),
            "route_counts": pd.DataFrame(),
            "dose_counts": pd.DataFrame(),
            "dose_form_counts": pd.DataFrame(),
            "dose_freq_counts": pd.DataFrame(),
            "reactions": pd.DataFrame(),
            "outcomes": pd.DataFrame(),
            "indications": pd.DataFrame(),
            "cases": pd.DataFrame(),
        }
    queried_ids_sql = ids_sql
    if matched_names:
        queried_ids_sql = _ids_sql_for_drug(matched_names, quarters, role_filter)

    with ThreadPoolExecutor(max_workers=10) as pool:
        f_dose = pool.submit(
            _run_sql,
            f"""
            SELECT dose, COUNT(DISTINCT primaryid) AS n_cases
            FROM (
              SELECT CAST(d.primaryid AS STRING) AS primaryid,
                     TRIM(CONCAT(COALESCE(CAST(d.dose_amt AS STRING), ''), ' ', COALESCE(CAST(d.dose_unit AS STRING), ''))) AS dose
              FROM {_table("drug_records_slim")} d
              INNER JOIN ({ids_sql}) ids ON CAST(d.primaryid AS STRING)=ids.primaryid
            ) x
            GROUP BY dose
            ORDER BY n_cases DESC
            LIMIT {int(top_n)}
            """,
        )
        f_ingredients = pool.submit(_top_counts_by_ids, "drug_records_slim", "prod_ai", top_n, queried_ids_sql)
        f_role = pool.submit(_top_counts_by_ids, "drug_records_slim", "role_cod", top_n, ids_sql)
        f_route = pool.submit(_top_counts_by_ids, "drug_records_slim", "route", top_n, ids_sql)
        f_dose_form = pool.submit(_top_counts_by_ids, "drug_records_slim", "dose_form", top_n, ids_sql)
        f_dose_freq = pool.submit(_top_counts_by_ids, "drug_records_slim", "dose_freq", top_n, ids_sql)
        f_reactions = pool.submit(_top_counts_by_ids, "reac_slim", "pt", top_n, ids_sql)
        f_outcomes = pool.submit(_top_counts_by_ids, "outc_slim", "outc_cod", top_n, ids_sql)
        f_indications = pool.submit(_top_counts_by_ids, "indi_slim", "indi_pt", top_n, ids_sql)
        f_cases = pool.submit(_build_case_table, ids_sql, True)

        return {
            "ingredients": f_ingredients.result().rename(columns={"prod_ai": "ingredient"}),
            "role_counts": f_role.result(),
            "route_counts": f_route.result(),
            "dose_counts": f_dose.result(),
            "dose_form_counts": f_dose_form.result(),
            "dose_freq_counts": f_dose_freq.result(),
            "reactions": f_reactions.result(),
            "outcomes": f_outcomes.result(),
            "indications": f_indications.result(),
            "cases": f_cases.result(),
        }


def drug_manufacturer_bundle(
    primaryids: tuple[str, ...],
    top_n: int,
    role_filter: str,
    quarters: tuple[str, ...],
    matched_names: tuple[str, ...] = (),
) -> dict[str, Any]:
    from concurrent.futures import ThreadPoolExecutor

    ids_sql = (
        _ids_sql_for_drug(matched_names, quarters, role_filter)
        if matched_names
        else _ids_sql_from_primaryids(primaryids)
    )
    if _ids_count(ids_sql) == 0:
        return {
            "ingredients": pd.DataFrame(),
            "manufacturer_counts": pd.DataFrame(),
            "country_counts": pd.DataFrame(),
            "outcome_counts": pd.DataFrame(),
            "dose_form_counts": pd.DataFrame(),
            "cases": pd.DataFrame(),
            "quarterly_trend": pd.DataFrame(),
        }
    queried_ids_sql = ids_sql
    if matched_names:
        queried_ids_sql = _ids_sql_for_drug(matched_names, quarters, role_filter)

    with ThreadPoolExecutor(max_workers=7) as pool:
        f_trend = pool.submit(
            _run_sql,
            f"SELECT CAST(d.year_q AS STRING) AS year_q, COUNT(DISTINCT CAST(d.primaryid AS STRING)) AS n_cases FROM {_table('demo_slim')} d INNER JOIN ({ids_sql}) ids ON CAST(d.primaryid AS STRING)=ids.primaryid GROUP BY CAST(d.year_q AS STRING) ORDER BY year_q",
        )
        f_cases = pool.submit(_build_case_table, ids_sql)
        f_ingredients = pool.submit(_top_counts_by_ids, "drug_records_slim", "prod_ai", top_n, queried_ids_sql)
        f_mfr = pool.submit(_top_counts_by_ids, "demo_slim", "canonical_mfr", top_n, ids_sql)
        f_country = pool.submit(_top_counts_by_ids, "demo_slim", "occr_country", top_n, ids_sql)
        f_outcomes = pool.submit(_top_counts_by_ids, "outc_slim", "outc_cod", top_n, ids_sql)
        f_dose_form = pool.submit(_top_counts_by_ids, "drug_records_slim", "dose_form", top_n, ids_sql)

        cases = f_cases.result()
        if not cases.empty:
            keep = [
                "event_dt",
                "manufacturer",
                "country",
                "active_ingredient",
                "dose_form",
                "outcomes",
            ]
            cases = cases[keep].sort_values("event_dt", ascending=False)

        return {
            "ingredients": f_ingredients.result().rename(columns={"prod_ai": "ingredient"}),
            "manufacturer_counts": f_mfr.result().rename(columns={"canonical_mfr": "manufacturer"}),
            "country_counts": f_country.result().rename(columns={"occr_country": "country"}),
            "outcome_counts": f_outcomes.result(),
            "dose_form_counts": f_dose_form.result(),
            "cases": cases,
            "quarterly_trend": f_trend.result(),
        }


def manufacturer_query_bundle(
    canonical_names: tuple[str, ...],
    top_n: int,
    role_filter: str,
    quarters: tuple[str, ...],
) -> dict[str, Any]:
    from concurrent.futures import ThreadPoolExecutor

    ids_sql = _ids_sql_for_manufacturer(canonical_names, quarters, role_filter)
    if _ids_count(ids_sql) == 0:
        return {
            "kpi": _kpi_from_ids(ids_sql),
            "drug_counts": pd.DataFrame(),
            "ingredient_counts": pd.DataFrame(),
            "outcome_counts": pd.DataFrame(),
            "indication_counts": pd.DataFrame(),
            "country_counts": pd.DataFrame(),
            "cases": pd.DataFrame(),
            "quarterly_trend": pd.DataFrame(),
        }

    with ThreadPoolExecutor(max_workers=10) as pool:
        f_trend = pool.submit(
            _run_sql,
            f"SELECT CAST(d.year_q AS STRING) AS year_q, COUNT(DISTINCT CAST(d.primaryid AS STRING)) AS n_cases FROM {_table('demo_slim')} d INNER JOIN ({ids_sql}) ids ON CAST(d.primaryid AS STRING)=ids.primaryid GROUP BY CAST(d.year_q AS STRING) ORDER BY year_q",
        )
        f_cases = pool.submit(_build_case_table, ids_sql)
        f_drug_names = pool.submit(
            _run_sql,
            f"SELECT CAST(d.primaryid AS STRING) AS primaryid, FIRST(CAST(d.drugname AS STRING), true) AS drug_name FROM {_table('drug_records_slim')} d INNER JOIN ({ids_sql}) ids ON CAST(d.primaryid AS STRING)=ids.primaryid GROUP BY CAST(d.primaryid AS STRING)",
        )
        f_kpi = pool.submit(_kpi_from_ids, ids_sql)
        f_unique_drugs = pool.submit(
            _run_sql,
            f"SELECT COUNT(DISTINCT CAST(d.drugname AS STRING)) AS n FROM {_table('drug_records_slim')} d INNER JOIN ({ids_sql}) ids ON CAST(d.primaryid AS STRING)=ids.primaryid WHERE TRIM(CAST(d.drugname AS STRING)) <> ''",
        )
        f_unique_countries = pool.submit(
            _run_sql,
            f"SELECT COUNT(DISTINCT CAST(d.occr_country AS STRING)) AS n FROM {_table('demo_slim')} d INNER JOIN ({ids_sql}) ids ON CAST(d.primaryid AS STRING)=ids.primaryid WHERE TRIM(CAST(d.occr_country AS STRING)) <> ''",
        )
        f_drug_counts = pool.submit(_top_counts_by_ids, "drug_records_slim", "drugname", top_n, ids_sql)
        f_ingredients = pool.submit(_top_counts_by_ids, "drug_records_slim", "prod_ai", top_n, ids_sql)
        f_outcomes = pool.submit(_top_counts_by_ids, "outc_slim", "outc_cod", top_n, ids_sql)
        f_indications = pool.submit(_top_counts_by_ids, "indi_slim", "indi_pt", top_n, ids_sql)
        f_countries = pool.submit(_top_counts_by_ids, "demo_slim", "occr_country", top_n, ids_sql)

        table = f_cases.result()
        drug_name_by_id = f_drug_names.result()
        if not table.empty and not drug_name_by_id.empty:
            dmap = dict(
                zip(
                    drug_name_by_id["primaryid"].astype(str),
                    drug_name_by_id["drug_name"].astype(str),
                )
            )
            table["drug_name"] = table["primaryid"].map(lambda x: dmap.get(str(x), ""))
            table = table[
                [
                    "event_dt",
                    "drug_name",
                    "active_ingredient",
                    "country",
                    "outcomes",
                    "top_indication",
                ]
            ].sort_values("event_dt", ascending=False)

        kpi = f_kpi.result()
        kpi["unique_drugs"] = int(f_unique_drugs.result().iloc[0]["n"])
        kpi["countries"] = int(f_unique_countries.result().iloc[0]["n"])

        return {
            "kpi": kpi,
            "drug_counts": f_drug_counts.result(),
            "ingredient_counts": f_ingredients.result().rename(columns={"prod_ai": "ingredient"}),
            "outcome_counts": f_outcomes.result(),
            "indication_counts": f_indications.result(),
            "country_counts": f_countries.result().rename(columns={"occr_country": "country"}),
            "cases": table,
            "quarterly_trend": f_trend.result(),
        }


def reaction_kpis(
    terms: tuple[str, ...], quarters: tuple[str, ...], role_filter: str
) -> dict[str, Any]:
    ids_sql = _ids_sql_for_reaction(terms, quarters, role_filter)
    out = _kpi_from_ids(ids_sql)
    out["n_terms"] = len(terms)
    return out


def reaction_top_drugs(
    terms: tuple[str, ...], top_n: int, quarters: tuple[str, ...], role_filter: str
) -> pd.DataFrame:
    ids_sql = _ids_sql_for_reaction(terms, quarters, role_filter)
    return _top_counts_by_ids("drug_records_slim", "drugname", top_n, ids_sql)


def reaction_outcomes(
    terms: tuple[str, ...], top_n: int, quarters: tuple[str, ...], role_filter: str
) -> pd.DataFrame:
    ids_sql = _ids_sql_for_reaction(terms, quarters, role_filter)
    return _top_counts_by_ids("outc_slim", "outc_cod", top_n, ids_sql)


def reaction_trend(
    terms: tuple[str, ...], quarters: tuple[str, ...], role_filter: str
) -> pd.DataFrame:
    ids_sql = _ids_sql_for_reaction(terms, quarters, role_filter)
    return _run_sql(
        f"SELECT CAST(d.year_q AS STRING) AS year_q, COUNT(DISTINCT CAST(d.primaryid AS STRING)) AS n_cases FROM {_table('demo_slim')} d INNER JOIN ({ids_sql}) ids ON CAST(d.primaryid AS STRING)=ids.primaryid GROUP BY CAST(d.year_q AS STRING) ORDER BY year_q"
    )
