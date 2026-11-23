-- Q05 — Count purchases in one department
--
-- What it answers: "How many purchases were in the Games department?"
-- Route:           GET /stats/department_count   (params: department; every route also takes db=)
-- Pattern:         counting_and_summaries
-- Engine:          PostgreSQL
--
-- Think about it:
-- Find "Index Only Scan" and "Heap Fetches" in the idx_* plan. What does
-- Heap Fetches count, and what would make it go up? (07_explain/ has an
-- experiment.)

SELECT COUNT(*) AS num_purchases
FROM purchases
WHERE department = %(department)s;
