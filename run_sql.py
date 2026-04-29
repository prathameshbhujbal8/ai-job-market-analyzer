"""
run_sql.py — Execute SQL analysis on job_data.csv using DuckDB
No database server required. DuckDB reads the CSV directly.

INSTALL: pip install duckdb pandas
RUN    : python run_sql.py
"""

import duckdb
import pandas as pd

CSV_PATH = "data/job_data.csv"

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 120)
pd.set_option("display.float_format", "{:.2f}".format)


def section(title):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def run(con, title, sql):
    section(title)
    result = con.execute(sql).df()
    print(result.to_string(index=False))
    return result


# ── CONNECT & LOAD ────────────────────────────────────────────
con = duckdb.connect()

con.execute(f"""
    CREATE OR REPLACE TABLE jobs AS
    SELECT
        job_title,
        company,
        job_location,
        search_city,
        search_country,
        "job level"       AS job_level,
        job_type,
        job_skills,
        LOWER(job_skills) AS skills_lower
    FROM read_csv_auto('{CSV_PATH}', ignore_errors = true)
""")

total_jobs = con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
print(f"\n[INFO] Loaded {total_jobs:,} rows from {CSV_PATH}")


# ── 1. DATASET OVERVIEW ───────────────────────────────────────
run(con, "1. DATASET OVERVIEW", """
    SELECT
        COUNT(*)                                       AS total_jobs,
        COUNT(*) FILTER (WHERE job_skills IS NOT NULL) AS jobs_with_skills,
        COUNT(DISTINCT company)                        AS unique_companies,
        COUNT(DISTINCT search_country)                 AS countries,
        COUNT(DISTINCT job_level)                      AS seniority_levels
    FROM jobs
""")


# ── 2. OVERALL SKILL DEMAND ───────────────────────────────────
run(con, "2. OVERALL SKILL DEMAND (%)", f"""
    SELECT skill_name,
           skill_count,
           {total_jobs} AS total_jobs,
           ROUND(skill_count * 100.0 / {total_jobs}, 2) AS demand_pct
    FROM (
        SELECT 'SQL'               AS skill_name, COUNT(*) FILTER (WHERE skills_lower LIKE '%sql%')             AS skill_count FROM jobs
        UNION ALL SELECT 'Excel',               COUNT(*) FILTER (WHERE skills_lower LIKE '%excel%')             FROM jobs
        UNION ALL SELECT 'Python',              COUNT(*) FILTER (WHERE skills_lower LIKE '%python%')            FROM jobs
        UNION ALL SELECT 'Power BI',            COUNT(*) FILTER (WHERE skills_lower LIKE '%power bi%')          FROM jobs
        UNION ALL SELECT 'Tableau',             COUNT(*) FILTER (WHERE skills_lower LIKE '%tableau%')           FROM jobs
        UNION ALL SELECT 'R',                   COUNT(*) FILTER (WHERE regexp_matches(skills_lower, '\\br\\b')) FROM jobs
        UNION ALL SELECT 'Statistics',          COUNT(*) FILTER (WHERE skills_lower LIKE '%statistics%')        FROM jobs
        UNION ALL SELECT 'Data Visualization',  COUNT(*) FILTER (WHERE skills_lower LIKE '%data visualization%') FROM jobs
        UNION ALL SELECT 'Machine Learning',    COUNT(*) FILTER (WHERE skills_lower LIKE '%machine learning%')  FROM jobs
        UNION ALL SELECT 'SAS',                 COUNT(*) FILTER (WHERE regexp_matches(skills_lower, '\\bsas\\b')) FROM jobs
        UNION ALL SELECT 'AWS',                 COUNT(*) FILTER (WHERE regexp_matches(skills_lower, '\\baws\\b')) FROM jobs
        UNION ALL SELECT 'Looker',              COUNT(*) FILTER (WHERE skills_lower LIKE '%looker%')            FROM jobs
    ) t
    ORDER BY demand_pct DESC
""")


# ── 3. SKILL DEMAND BY JOB LEVEL (CORRECT VERSION) ───────────
# Reads: "Of Associate jobs, what % require SQL?"
# (Previous version was wrong — it measured share of SQL jobs, not SQL demand per level)
run(con, "3. SKILL DEMAND BY JOB LEVEL", """
    SELECT
        job_level,
        COUNT(*) AS total_jobs,
        ROUND(SUM(CASE WHEN skills_lower LIKE '%sql%'     THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS sql_pct,
        ROUND(SUM(CASE WHEN skills_lower LIKE '%excel%'   THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS excel_pct,
        ROUND(SUM(CASE WHEN skills_lower LIKE '%python%'  THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS python_pct,
        ROUND(SUM(CASE WHEN skills_lower LIKE '%power bi%'THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS powerbi_pct,
        ROUND(SUM(CASE WHEN skills_lower LIKE '%tableau%' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS tableau_pct
    FROM jobs
    WHERE job_level IS NOT NULL
    GROUP BY job_level
    ORDER BY job_level
""")


# ── 4. SKILL DEMAND BY WORK TYPE ─────────────────────────────
run(con, "4. SKILL DEMAND BY WORK TYPE (Remote / Onsite / Hybrid)", """
    SELECT
        job_type,
        COUNT(*) AS total_jobs,
        ROUND(SUM(CASE WHEN skills_lower LIKE '%sql%'      THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS sql_pct,
        ROUND(SUM(CASE WHEN skills_lower LIKE '%excel%'    THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS excel_pct,
        ROUND(SUM(CASE WHEN skills_lower LIKE '%python%'   THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS python_pct,
        ROUND(SUM(CASE WHEN skills_lower LIKE '%power bi%' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS powerbi_pct
    FROM jobs
    WHERE job_type IS NOT NULL
    GROUP BY job_type
    ORDER BY total_jobs DESC
""")


# ── 5. SENIORITY × WORK TYPE CROSS-TAB (PIVOT-STYLE) ─────────
run(con, "5. JOB LEVEL × WORK TYPE CROSS-TAB", """
    SELECT
        job_level,
        job_type,
        COUNT(*) AS job_count,
        ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY job_level), 2) AS pct_within_level
    FROM jobs
    WHERE job_level IS NOT NULL AND job_type IS NOT NULL
    GROUP BY job_level, job_type
    ORDER BY job_level, job_count DESC
""")


# ── 6. SKILL CO-OCCURRENCE WITH SQL ──────────────────────────
run(con, "6. SKILLS MOST COMMON ALONGSIDE SQL (Co-occurrence)", f"""
    WITH sql_jobs AS (
        SELECT skills_lower FROM jobs WHERE skills_lower LIKE '%sql%'
    )
    SELECT
        skill_name,
        skill_count,
        (SELECT COUNT(*) FROM sql_jobs) AS sql_total,
        ROUND(skill_count * 100.0 / (SELECT COUNT(*) FROM sql_jobs), 2) AS co_occurrence_pct
    FROM (
        SELECT 'Python'           AS skill_name, COUNT(*) FILTER (WHERE skills_lower LIKE '%python%')           AS skill_count FROM sql_jobs
        UNION ALL SELECT 'Excel',               COUNT(*) FILTER (WHERE skills_lower LIKE '%excel%')             FROM sql_jobs
        UNION ALL SELECT 'Tableau',             COUNT(*) FILTER (WHERE skills_lower LIKE '%tableau%')           FROM sql_jobs
        UNION ALL SELECT 'Power BI',            COUNT(*) FILTER (WHERE skills_lower LIKE '%power bi%')          FROM sql_jobs
        UNION ALL SELECT 'R',                   COUNT(*) FILTER (WHERE regexp_matches(skills_lower, '\\br\\b')) FROM sql_jobs
        UNION ALL SELECT 'Machine Learning',    COUNT(*) FILTER (WHERE skills_lower LIKE '%machine learning%')  FROM sql_jobs
        UNION ALL SELECT 'Statistics',          COUNT(*) FILTER (WHERE skills_lower LIKE '%statistics%')        FROM sql_jobs
    ) t
    ORDER BY co_occurrence_pct DESC
""")


# ── 7. TOP 15 HIRING COMPANIES ────────────────────────────────
run(con, "7. TOP 15 HIRING COMPANIES", """
    SELECT company, COUNT(*) AS job_postings
    FROM jobs
    WHERE company IS NOT NULL
    GROUP BY company
    ORDER BY job_postings DESC
    LIMIT 15
""")


# ── 8. SKILL STACK SEGMENTATION (CASE WHEN) ──────────────────
run(con, "8. SKILL STACK SEGMENTATION", f"""
    SELECT
        stack_type,
        COUNT(*) AS job_count,
        ROUND(COUNT(*) * 100.0 / {total_jobs}, 2) AS pct_of_total
    FROM (
        SELECT
            CASE
                WHEN skills_lower LIKE '%sql%' AND skills_lower LIKE '%python%'   THEN 'SQL + Python'
                WHEN skills_lower LIKE '%sql%' AND skills_lower LIKE '%power bi%' THEN 'SQL + Power BI'
                WHEN skills_lower LIKE '%sql%' AND skills_lower LIKE '%tableau%'  THEN 'SQL + Tableau'
                WHEN skills_lower LIKE '%sql%' AND skills_lower LIKE '%excel%'    THEN 'SQL + Excel only'
                WHEN skills_lower LIKE '%sql%'                                    THEN 'SQL only'
                WHEN skills_lower LIKE '%excel%'                                  THEN 'Excel only'
                ELSE 'Other / No core skill'
            END AS stack_type
        FROM jobs
    ) s
    GROUP BY stack_type
    ORDER BY job_count DESC
""")

print("\n[DONE] All queries executed successfully.\n")
con.close()