-- Q06 — A customer's purchase streaks
--
-- What it answers: "What were this customer's longest runs of buying something on consecutive days?"
-- Route:           GET /customers/streaks   (params: customer_id; every route also takes db=)
-- Pattern:         gaps_and_islands
-- Engine:          PostgreSQL
--
-- Think about it:
-- The idx_* plan uses an index that starts with purchase_date, yet the query
-- filters on customer_id. Find "Index Searches" in the plan. How can an index
-- help when its first column isn't in the WHERE? (This is new in
-- PostgreSQL 18.)

WITH days AS (
    SELECT DISTINCT purchase_date AS day
    FROM purchases
    WHERE customer_id = %(customer_id)s
),
islands AS (
    SELECT day,
           day - (ROW_NUMBER() OVER (ORDER BY day))::int AS grp
    FROM days
)
SELECT MIN(day) AS streak_start, MAX(day) AS streak_end, COUNT(*) AS days
FROM islands
GROUP BY grp
HAVING COUNT(*) >= 2
ORDER BY days DESC, streak_start
LIMIT 10;
