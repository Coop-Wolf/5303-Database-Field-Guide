-- Q06 — A customer's purchase streaks
--
-- What it answers: "What were this customer's longest runs of buying something on consecutive days?"
-- Route:           GET /customers/streaks   (params: customer_id; every route also takes db=)
-- Pattern:         gaps_and_islands
-- Engine:          DuckDB
--
-- Think about it:
-- purchase_date is a real DATE here, so a date minus an integer is a date.
-- Work out by hand why consecutive days minus their row numbers land in the
-- same group. Is the expensive step the same one it was in SQLite?

WITH days AS (
    SELECT DISTINCT purchase_date AS day
    FROM purchases
    WHERE customer_id = $customer_id
),
islands AS (
    SELECT day,
           day - CAST(ROW_NUMBER() OVER (ORDER BY day) AS INTEGER) AS grp
    FROM days
)
SELECT MIN(day) AS streak_start, MAX(day) AS streak_end, COUNT(*) AS days
FROM islands
GROUP BY grp
HAVING COUNT(*) >= 2
ORDER BY days DESC, streak_start
LIMIT 10;
