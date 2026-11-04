-- Q14 — State × department × month report (multi-CTE)
--
-- What it answers: "For 2025, which (state, department, month) combinations had at least 10 purchases, and which brought in the most revenue?"
-- Route:           GET /reports/cube   (params: start, end, min_purchases; every route also takes db=)
-- Pattern:         multi_cte_reports
-- Engine:          DuckDB
--
-- Think about it:
-- DuckDB could write this as one GROUP BY CUBE. It's kept as CTEs so both
-- engines run the same query. Compare idx_* and noidx_*, then compare with
-- what you found for Q14 in SQLite. The fast version reads monthly_sales:
-- check its grain against this query's GROUP BY.

WITH base AS (
    SELECT z.state_code, pu.department,
           strftime(pu.purchase_date, '%Y-%m') AS month, pu.amount
    FROM purchases pu
    JOIN customers c ON c.customer_id = pu.customer_id
    JOIN zipcodes  z ON z.zipcode     = c.zipcode
    WHERE pu.purchase_date >= $start AND pu.purchase_date < $end
),
cube AS (
    SELECT state_code, department, month,
           COUNT(*) AS num_purchases, SUM(amount) AS revenue
    FROM base
    GROUP BY state_code, department, month
)
SELECT state_code, department, month, num_purchases, ROUND(revenue, 2) AS revenue
FROM cube
WHERE num_purchases >= $min_purchases
ORDER BY revenue DESC, state_code, department, month  -- tiebreakers: same rows every time
LIMIT 50;
