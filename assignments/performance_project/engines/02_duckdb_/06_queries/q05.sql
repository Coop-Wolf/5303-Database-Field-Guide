-- Q05 — Count purchases in one department
--
-- What it answers: "How many purchases were in the Games department?"
-- Route:           GET /stats/department_count   (params: department; every route also takes db=)
-- Pattern:         counting_and_summaries
-- Engine:          DuckDB
--
-- Think about it:
-- SQLite answered this from a covering index. DuckDB has no covering
-- indexes. How many rows does the plan say it scanned, and how many of the
-- table's columns did it actually have to read? Then compare idx_* and
-- noidx_*: same plan, different time?

SELECT COUNT(*) AS num_purchases
FROM purchases
WHERE department = $department;
