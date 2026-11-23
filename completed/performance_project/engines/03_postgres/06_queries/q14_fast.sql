-- Q14 (fast) — State × department × month report (multi-CTE)
--
-- What it answers: "For 2025, which (state, department, month) combinations had at least 10 purchases, and which brought in the most revenue?"
-- Route:           GET /reports/cube/fast   (params: start, end, min_purchases; every route also takes db=)
-- Pattern:         multi_cte_reports
-- Engine:          PostgreSQL
--
-- Think about it:
-- In SQLite, idx_* was slower than noidx_*: one table lookup per purchase.
-- PostgreSQL reaches the same rows through a Bitmap Heap Scan. What does the
-- bitmap change about how the table is read? Then compare idx_* and noidx_* at
-- 100k and at 1m. Does the answer stay the same?

SELECT state_code, department, month, num_purchases, ROUND(revenue, 2) AS revenue
FROM monthly_sales
WHERE month >= substr(%(start)s, 1, 7) AND month < substr(%(end)s, 1, 7)
  AND num_purchases >= %(min_purchases)s
ORDER BY revenue DESC, state_code, department, month  -- tiebreakers: same rows every time
LIMIT 50;
