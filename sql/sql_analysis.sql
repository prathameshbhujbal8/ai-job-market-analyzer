-- ============================================================
-- sql_analysis.sql — Job Market Skill Demand Analysis
-- Engine : DuckDB (reads CSV directly, no server needed)
-- Dataset: data/job_data.csv (12,894 analyst job postings)
--
-- To run: python run_sql.py
--         (run_sql.py executes all queries and prints results)
-- ============================================================


-- ── 0. LOAD ──────────────────────────────────────────────────
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
FROM read_csv_auto('data/job_data.csv', ignore_errors = true);


-- ── 1. DATASET OVERVIEW ──────────────────────────────────────
SELECT
    COUNT(*)                                       AS total_jobs,
    COUNT(*) FILTER (WHERE job_skills IS NOT NULL) AS jobs_with_skills,
    COUNT(DISTINCT company)                        AS unique_companies,
    COUNT(DISTINCT search_country)                 AS countries,
    COUNT(DISTINCT job_level)                      AS seniority_levels
FROM jobs;


-- ── 2. OVERALL SKILL DEMAND ──────────────────────────────────
-- % of all postings that mention each skill.
-- Uses LIKE for multi-word skills, regexp_matches(\b) for single-letter skills
-- to prevent false matches (e.g. 'r' inside 'market').

SELECT skill_name,
       skill_count,
       (SELECT COUNT(*) FROM jobs) AS total_jobs,
       ROUND(skill_count * 100.0 / (SELECT COUNT(*) FROM jobs), 2) AS demand_pct
FROM (
    SELECT 'SQL'              AS skill_name, COUNT(*) FILTER (WHERE skills_lower LIKE '%sql%')              AS skill_count FROM jobs
    UNION ALL SELECT 'Excel',              COUNT(*) FILTER (WHERE skills_lower LIKE '%excel%')              FROM jobs
    UNION ALL SELECT 'Python',             COUNT(*) FILTER (WHERE skills_lower LIKE '%python%')             FROM jobs
    UNION ALL SELECT 'Power BI',           COUNT(*) FILTER (WHERE skills_lower LIKE '%power bi%')           FROM jobs
    UNION ALL SELECT 'Tableau',            COUNT(*) FILTER (WHERE skills_lower LIKE '%tableau%')            FROM jobs
    UNION ALL SELECT 'R',                  COUNT(*) FILTER (WHERE regexp_matches(skills_lower, '\br\b'))    FROM jobs
    UNION ALL SELECT 'Statistics',         COUNT(*) FILTER (WHERE skills_lower LIKE '%statistics%')         FROM jobs
    UNION ALL SELECT 'Data Visualization', COUNT(*) FILTER (WHERE skills_lower LIKE '%data visualization%') FROM jobs
    UNION ALL SELECT 'Machine Learning',   COUNT(*) FILTER (WHERE skills_lower LIKE '%machine learning%')   FROM jobs
    UNION ALL SELECT 'SAS',               COUNT(*) FILTER (WHERE regexp_matches(skills_lower, '\bsas\b'))   FROM jobs
    UNION ALL SELECT 'AWS',               COUNT(*) FILTER (WHERE regexp_matches(skills_lower, '\baws\b'))   FROM jobs
) t
ORDER BY demand_pct DESC;

/*
Expected top results:
  SQL              → 37.11%
  Excel            → 29.16%
  Data Viz         → 18.37%
  Python           → 17.16%
  Tableau          → 17.02%
  Power BI         → 15.03%
*/


-- ── 3. SKILL DEMAND BY JOB LEVEL ─────────────────────────────
-- CORRECT QUERY: "Of Associate jobs, what % require SQL?"
-- (A common wrong version filters to SQL jobs first and then groups —
--  that answers a different question: "Of SQL jobs, what share are Associate?")

SELECT
    job_level,
    COUNT(*) AS total_jobs,
    ROUND(SUM(CASE WHEN skills_lower LIKE '%sql%'      THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS sql_pct,
    ROUND(SUM(CASE WHEN skills_lower LIKE '%excel%'    THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS excel_pct,
    ROUND(SUM(CASE WHEN skills_lower LIKE '%python%'   THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS python_pct,
    ROUND(SUM(CASE WHEN skills_lower LIKE '%power bi%' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS powerbi_pct,
    ROUND(SUM(CASE WHEN skills_lower LIKE '%tableau%'  THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS tableau_pct
FROM jobs
WHERE job_level IS NOT NULL
GROUP BY job_level
ORDER BY job_level;

/*
Expected:
  job_level  | total | sql_pct | excel_pct | python_pct | powerbi_pct | tableau_pct
  Associate  | 3203  | 35.60   | 32.90     | 16.20      | 11.90       | 15.50
  Mid senior | 9691  | 38.20   | 28.30     | 17.50      | 16.10       | 17.50

Insight: Power BI demand +4.2pp at Mid-Senior. Excel -4.6pp (baseline skill).
*/


-- ── 4. SKILL DEMAND BY WORK TYPE ─────────────────────────────
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
ORDER BY total_jobs DESC;

/*
Expected:
  Onsite  → SQL 36.48%, Excel 27.60%, Python 16.96%
  Hybrid  → SQL 36.40%, Excel 34.40%, Python 15.70%
  Remote  → SQL 42.28%, Excel 24.60%, Python 21.27%

Insight: Remote roles demand 5.8pp more SQL. Target SQL if applying remotely.
*/


-- ── 5. SENIORITY × WORK TYPE CROSS-TAB ──────────────────────
-- Two-dimensional breakdown using WINDOW function.
-- Equivalent to an Excel pivot table with two row fields.

SELECT
    job_level,
    job_type,
    COUNT(*) AS job_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY job_level), 2) AS pct_within_level,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2)                       AS pct_of_all_jobs
FROM jobs
WHERE job_level IS NOT NULL
  AND job_type  IS NOT NULL
GROUP BY job_level, job_type
ORDER BY job_level, job_count DESC;


-- ── 6. SKILL CO-OCCURRENCE WITH SQL ──────────────────────────
-- Which skills most often appear alongside SQL?
-- Uses CTE + subquery — demonstrates structured SQL thinking.

WITH sql_jobs AS (
    SELECT skills_lower
    FROM   jobs
    WHERE  skills_lower LIKE '%sql%'
)
SELECT
    skill_name,
    skill_count,
    (SELECT COUNT(*) FROM sql_jobs)                                      AS sql_job_count,
    ROUND(skill_count * 100.0 / (SELECT COUNT(*) FROM sql_jobs), 2)     AS co_occurrence_pct
FROM (
    SELECT 'Python'          AS skill_name, COUNT(*) FILTER (WHERE skills_lower LIKE '%python%')          AS skill_count FROM sql_jobs
    UNION ALL SELECT 'Excel',              COUNT(*) FILTER (WHERE skills_lower LIKE '%excel%')             FROM sql_jobs
    UNION ALL SELECT 'Tableau',            COUNT(*) FILTER (WHERE skills_lower LIKE '%tableau%')           FROM sql_jobs
    UNION ALL SELECT 'Power BI',           COUNT(*) FILTER (WHERE skills_lower LIKE '%power bi%')          FROM sql_jobs
    UNION ALL SELECT 'R',                  COUNT(*) FILTER (WHERE regexp_matches(skills_lower, '\br\b'))   FROM sql_jobs
    UNION ALL SELECT 'Machine Learning',   COUNT(*) FILTER (WHERE skills_lower LIKE '%machine learning%')  FROM sql_jobs
    UNION ALL SELECT 'Statistics',         COUNT(*) FILTER (WHERE skills_lower LIKE '%statistics%')        FROM sql_jobs
) t
ORDER BY co_occurrence_pct DESC;

/*
Expected (of SQL jobs, % that also require...):
  Python         → ~38%    Tableau → ~37%
  Excel          → ~34%    Power BI → ~28%
  Insight: Core DA stack = SQL + Python + Tableau/Power BI
*/


-- ── 7. TOP 15 HIRING COMPANIES ────────────────────────────────
SELECT
    company,
    COUNT(*) AS job_postings
FROM jobs
WHERE company IS NOT NULL
GROUP BY company
ORDER BY job_postings DESC
LIMIT 15;


-- ── 8. SKILL STACK SEGMENTATION (CASE WHEN) ──────────────────
-- Classify each job by which skill combination it requires.

SELECT
    stack_type,
    COUNT(*) AS job_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct_of_total
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
ORDER BY job_count DESC;