-- Q07 — 90-day spending leaderboard
--
-- What it answers: "Who were the top 20 spenders in the last 90 days, and what rank is each?"
-- Route:           GET /stats/leaderboard   (params: start, end; every route also takes db=)
-- Pattern:         window_ranking
-- Engine:          DuckDB
--
-- Think about it:
-- No index helps this in DuckDB, in either database. What work does every
-- version have to do? Run it in the shell with .timer on, then again after
-- SET threads = 1. How much of the speed came from using every core?

WITH spend AS (
    SELECT customer_id, SUM(amount) AS total
    FROM purchases
    WHERE purchase_date >= $start AND purchase_date < $end
    GROUP BY customer_id
)
SELECT customer_id, ROUND(total, 2) AS total,
       RANK() OVER (ORDER BY total DESC) AS rank
FROM spend
ORDER BY total DESC, customer_id
LIMIT 20;
