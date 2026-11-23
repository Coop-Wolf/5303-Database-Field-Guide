-- Q14 — State × department × month report (multi-CTE)
--
-- What it answers: "For 2025, which (state, department, month) combinations had at least 10 purchases, and which brought in the most revenue?"
-- Route:           GET /reports/cube   (params: start, end, min_purchases; every route also takes db=)
-- Pattern:         multi_cte_reports
-- Engine:          PostgreSQL
--
-- Think about it:
-- In SQLite, idx_* was slower than noidx_*: one table lookup per purchase.
-- PostgreSQL reaches the same rows through a Bitmap Heap Scan. What does the
-- bitmap change about how the table is read? Then compare idx_* and noidx_* at
-- 100k and at 1m. Does the answer stay the same?

WITH base AS (
    SELECT z.state_code, pu.department,
           to_char(pu.purchase_date, 'YYYY-MM') AS month, pu.amount
    FROM purchases pu
    JOIN customers c ON c.customer_id = pu.customer_id
    JOIN zipcodes  z ON z.zipcode     = c.zipcode
    WHERE pu.purchase_date >= %(start)s AND pu.purchase_date < %(end)s
),
cube AS (
    SELECT state_code, department, month,
           COUNT(*) AS num_purchases, SUM(amount) AS revenue
    FROM base
    GROUP BY state_code, department, month
)
SELECT state_code, department, month, num_purchases, ROUND(revenue, 2) AS revenue
FROM cube
WHERE num_purchases >= %(min_purchases)s
ORDER BY revenue DESC, state_code, department, month  -- tiebreakers: same rows every time
LIMIT 50;
