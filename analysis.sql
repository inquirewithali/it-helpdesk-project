-- ============================================================
-- IT Help Desk Ticket Analysis
-- Compatible with: SQLite, PostgreSQL, DuckDB
-- Load data first:
--   .mode csv
--   .import data/tickets.csv tickets
-- ============================================================


-- ============================================================
-- 1. EXECUTIVE SUMMARY — Overall KPIs
-- ============================================================
SELECT
    COUNT(*)                                                        AS total_tickets,
    ROUND(100.0 * SUM(CASE WHEN status IN ('Resolved','Closed') THEN 1 ELSE 0 END) / COUNT(*), 1)
                                                                    AS resolution_rate_pct,
    ROUND(AVG(CASE WHEN resolution_hours != '' THEN CAST(resolution_hours AS REAL) END), 1)
                                                                    AS avg_resolution_hours,
    ROUND(100.0 * SUM(CASE WHEN met_sla = 'True' THEN 1 ELSE 0 END)
              / NULLIF(SUM(CASE WHEN met_sla != '' THEN 1 ELSE 0 END), 0), 1)
                                                                    AS sla_compliance_pct,
    ROUND(AVG(CASE WHEN satisfaction_score != '' THEN CAST(satisfaction_score AS REAL) END), 2)
                                                                    AS avg_csat_score
FROM tickets;


-- ============================================================
-- 2. TICKET VOLUME BY MONTH (trend analysis)
-- ============================================================
SELECT
    SUBSTR(created_at, 1, 7)        AS month,
    COUNT(*)                        AS ticket_count,
    SUM(CASE WHEN priority = 'P1 - Critical' THEN 1 ELSE 0 END) AS p1_count,
    SUM(CASE WHEN priority = 'P2 - High'     THEN 1 ELSE 0 END) AS p2_count
FROM tickets
GROUP BY month
ORDER BY month;


-- ============================================================
-- 3. SLA COMPLIANCE BY PRIORITY
-- ============================================================
SELECT
    priority,
    COUNT(*)                                                        AS total,
    SUM(CASE WHEN met_sla = 'True' THEN 1 ELSE 0 END)             AS met_sla,
    ROUND(100.0 * SUM(CASE WHEN met_sla = 'True' THEN 1 ELSE 0 END)
              / NULLIF(SUM(CASE WHEN met_sla != '' THEN 1 ELSE 0 END), 0), 1)
                                                                    AS sla_pct,
    ROUND(AVG(CASE WHEN resolution_hours != '' THEN CAST(resolution_hours AS REAL) END), 1)
                                                                    AS avg_hours
FROM tickets
GROUP BY priority
ORDER BY priority;


-- ============================================================
-- 4. TOP CATEGORIES BY VOLUME AND RESOLUTION TIME
-- ============================================================
SELECT
    category,
    COUNT(*)                                                        AS ticket_count,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM tickets), 1)    AS pct_of_total,
    ROUND(AVG(CASE WHEN resolution_hours != '' THEN CAST(resolution_hours AS REAL) END), 1)
                                                                    AS avg_resolution_hrs,
    ROUND(AVG(CASE WHEN satisfaction_score != '' THEN CAST(satisfaction_score AS REAL) END), 2)
                                                                    AS avg_csat
FROM tickets
GROUP BY category
ORDER BY ticket_count DESC;


-- ============================================================
-- 5. AGENT PERFORMANCE LEADERBOARD
-- ============================================================
SELECT
    assigned_agent,
    COUNT(*)                                                        AS tickets_handled,
    ROUND(AVG(CASE WHEN resolution_hours != '' THEN CAST(resolution_hours AS REAL) END), 1)
                                                                    AS avg_resolution_hrs,
    ROUND(100.0 * SUM(CASE WHEN met_sla = 'True' THEN 1 ELSE 0 END)
              / NULLIF(SUM(CASE WHEN met_sla != '' THEN 1 ELSE 0 END), 0), 1)
                                                                    AS sla_compliance_pct,
    ROUND(AVG(CASE WHEN satisfaction_score != '' THEN CAST(satisfaction_score AS REAL) END), 2)
                                                                    AS avg_csat,
    SUM(CASE WHEN priority IN ('P1 - Critical','P2 - High') THEN 1 ELSE 0 END)
                                                                    AS high_priority_handled
FROM tickets
GROUP BY assigned_agent
ORDER BY sla_compliance_pct DESC;


-- ============================================================
-- 6. DEPARTMENT BREAKDOWN — who submits the most tickets?
-- ============================================================
SELECT
    department,
    COUNT(*)                                                        AS ticket_count,
    ROUND(AVG(CASE WHEN resolution_hours != '' THEN CAST(resolution_hours AS REAL) END), 1)
                                                                    AS avg_resolution_hrs,
    SUM(CASE WHEN priority = 'P1 - Critical' THEN 1 ELSE 0 END)   AS p1_tickets,
    ROUND(AVG(CASE WHEN satisfaction_score != '' THEN CAST(satisfaction_score AS REAL) END), 2)
                                                                    AS avg_csat
FROM tickets
GROUP BY department
ORDER BY ticket_count DESC;


-- ============================================================
-- 7. REOPENED / CHRONIC ISSUES — same subject more than once
-- ============================================================
SELECT
    subject,
    category,
    COUNT(*)    AS occurrences,
    COUNT(DISTINCT department) AS departments_affected
FROM tickets
GROUP BY subject, category
HAVING COUNT(*) > 5
ORDER BY occurrences DESC
LIMIT 20;


-- ============================================================
-- 8. HOUR-OF-DAY SUBMISSION PATTERN (staffing insight)
-- ============================================================
SELECT
    CAST(SUBSTR(created_at, 12, 2) AS INTEGER)  AS hour_of_day,
    COUNT(*)                                     AS tickets_submitted
FROM tickets
GROUP BY hour_of_day
ORDER BY hour_of_day;


-- ============================================================
-- 9. LOW CSAT DEEP DIVE — tickets rated 1 or 2
-- ============================================================
SELECT
    category,
    priority,
    assigned_agent,
    COUNT(*)                                                        AS low_csat_tickets,
    ROUND(AVG(CAST(resolution_hours AS REAL)), 1)                  AS avg_resolution_hrs
FROM tickets
WHERE satisfaction_score IN ('1', '2')
GROUP BY category, priority, assigned_agent
ORDER BY low_csat_tickets DESC
LIMIT 15;


-- ============================================================
-- 10. BACKLOG — currently open tickets, oldest first
-- ============================================================
SELECT
    ticket_id,
    created_at,
    priority,
    category,
    subject,
    assigned_agent,
    status,
    ROUND(
        (julianday('now') - julianday(created_at)) * 24, 1
    ) AS age_hours
FROM tickets
WHERE status IN ('Open', 'In Progress', 'Pending User')
ORDER BY priority, created_at
LIMIT 30;
