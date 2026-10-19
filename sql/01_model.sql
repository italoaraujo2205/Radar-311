CREATE OR REPLACE TABLE stg_requests AS
WITH typed AS (
    SELECT
        NULLIF(TRIM(CAST(unique_key AS VARCHAR)), '') AS request_id,
        TRY_CAST(created_date AS TIMESTAMP) AS created_at,
        TRY_CAST(closed_date AS TIMESTAMP) AS closed_at,
        UPPER(TRIM(COALESCE(agency, 'UNKNOWN'))) AS agency,
        TRIM(COALESCE(complaint_type, 'UNKNOWN')) AS problem,
        NULLIF(TRIM(descriptor), '') AS problem_detail,
        UPPER(TRIM(COALESCE(borough, 'UNKNOWN'))) AS borough,
        NULLIF(TRIM(incident_zip), '') AS incident_zip,
        UPPER(TRIM(COALESCE(status, 'UNKNOWN'))) AS status,
        UPPER(TRIM(COALESCE(open_data_channel_type, 'UNKNOWN'))) AS channel,
        TRY_CAST(due_date AS TIMESTAMP) AS update_due_at
    FROM raw_requests
), ranked AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY request_id ORDER BY created_at DESC NULLS LAST) AS rn
    FROM typed
)
SELECT * EXCLUDE (rn),
       CASE WHEN request_id IS NULL THEN 'missing_key'
            WHEN created_at IS NULL THEN 'invalid_created_at'
            WHEN closed_at < created_at THEN 'closed_before_created'
            ELSE NULL END AS rejection_reason
FROM ranked WHERE rn = 1;

CREATE OR REPLACE TABLE rejected_requests AS
SELECT * FROM stg_requests WHERE rejection_reason IS NOT NULL;

CREATE OR REPLACE TABLE dim_problem AS
SELECT ROW_NUMBER() OVER (ORDER BY agency, problem) AS problem_key, agency, problem,
       COUNT(*) AS request_count
FROM stg_requests WHERE rejection_reason IS NULL GROUP BY agency, problem;

CREATE OR REPLACE TABLE dim_borough AS
SELECT ROW_NUMBER() OVER (ORDER BY borough) AS borough_key, borough,
       COUNT(*) AS request_count
FROM stg_requests WHERE rejection_reason IS NULL GROUP BY borough;

CREATE OR REPLACE TABLE fact_request AS
SELECT
    s.request_id, s.created_at, s.closed_at, s.update_due_at,
    p.problem_key, b.borough_key, s.status, s.channel, s.problem_detail,
    s.incident_zip,
    CAST(s.created_at <= CAST($as_of AS TIMESTAMP) - INTERVAL 72 HOUR
         AND NOT (s.status = 'CLOSED' AND s.closed_at IS NULL) AS INTEGER) AS eligible_72h,
    CAST(s.closed_at IS NOT NULL AND s.closed_at >= s.created_at
         AND s.closed_at <= s.created_at + INTERVAL 72 HOUR AS INTEGER) AS closed_72h,
    CASE WHEN s.closed_at IS NOT NULL
         THEN DATE_DIFF('minute', s.created_at, s.closed_at) / 60.0 END AS hours_to_close,
    CAST(s.closed_at IS NULL AND s.status <> 'CLOSED'
         AND s.created_at <= CAST($as_of AS TIMESTAMP) - INTERVAL 72 HOUR AS INTEGER)
         AS open_after_72h
FROM stg_requests s
JOIN dim_problem p USING (agency, problem)
JOIN dim_borough b USING (borough)
WHERE s.rejection_reason IS NULL AND s.created_at <= CAST($as_of AS TIMESTAMP);

CREATE OR REPLACE TABLE mart_daily AS
SELECT CAST(f.created_at AS DATE) AS created_day, p.agency, p.problem,
       COUNT(*) AS requests, SUM(f.eligible_72h) AS eligible_72h,
       SUM(CASE WHEN f.eligible_72h = 1 THEN f.closed_72h ELSE 0 END) AS closed_72h,
       SUM(f.open_after_72h) AS open_after_72h
FROM fact_request f JOIN dim_problem p USING (problem_key)
GROUP BY 1, 2, 3;

CREATE OR REPLACE TABLE mart_borough_problem AS
SELECT b.borough, p.agency, p.problem,
       COUNT(*) AS requests, SUM(f.eligible_72h) AS eligible_72h,
       SUM(CASE WHEN f.eligible_72h = 1 THEN f.closed_72h ELSE 0 END) AS closed_72h,
       SUM(f.open_after_72h) AS open_after_72h,
       ROUND(100.0 * SUM(CASE WHEN f.eligible_72h = 1 THEN f.closed_72h ELSE 0 END)
             / NULLIF(SUM(f.eligible_72h), 0), 2) AS pct_closed_72h,
       ROUND(QUANTILE_CONT(f.hours_to_close, 0.9), 1) AS p90_closed_hours
FROM fact_request f JOIN dim_problem p USING (problem_key)
JOIN dim_borough b USING (borough_key)
GROUP BY 1, 2, 3;

-- Cada bairro e comparado a bairros diferentes com a mesma agencia e tipo de problema.
-- Celulas sem pelo menos 30 casos comparaveis ficam fora do ajuste.
CREATE OR REPLACE TABLE mart_case_mix AS
WITH cells AS (
    SELECT *,
      SUM(eligible_72h) OVER (PARTITION BY agency, problem) - eligible_72h AS other_eligible,
      SUM(closed_72h) OVER (PARTITION BY agency, problem) - closed_72h AS other_closed
    FROM mart_borough_problem
), borough_scores AS (
    SELECT borough, SUM(eligible_72h) AS eligible_72h,
      SUM(CASE WHEN other_eligible >= 30 THEN eligible_72h ELSE 0 END) AS comparable,
      SUM(CASE WHEN other_eligible >= 30 THEN closed_72h ELSE 0 END) AS observed,
      SUM(CASE WHEN other_eligible >= 30 THEN eligible_72h * other_closed * 1.0 / other_eligible
               ELSE 0 END) AS expected
    FROM cells WHERE borough NOT IN ('UNKNOWN', 'UNSPECIFIED') GROUP BY borough
)
SELECT borough, eligible_72h, comparable, observed, ROUND(expected, 1) AS expected,
       ROUND(100.0 * comparable / NULLIF(eligible_72h, 0), 1) AS coverage_pct,
       ROUND(100.0 * (observed - expected) / NULLIF(comparable, 0), 2) AS adjusted_gap_pp
FROM borough_scores WHERE comparable >= 500 AND comparable >= 0.8 * eligible_72h;
