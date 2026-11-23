-- Q07 — 90-day spending leaderboard
--
-- What it answers: "Who were the top 20 spenders in the last 90 days, and what rank is each?"
-- Route:           GET /stats/leaderboard   (params: start, end; every route also takes db=)
-- Pattern:         window_ranking
-- Engine:          PostgreSQL
--
-- Think about it:
-- Both SQLite and PostgreSQL read the covering index here, and both gain
-- only about 2x from it. What work does every version still have to do before
-- anyone can be given a rank?

WITH spend AS (
    SELECT customer_id, SUM(amount) AS total
    FROM purchases
    WHERE purchase_date >= %(start)s AND purchase_date < %(end)s
    GROUP BY customer_id
)
SELECT customer_id, ROUND(total, 2) AS total,
       RANK() OVER (ORDER BY total DESC) AS rank
FROM spend
ORDER BY total DESC, customer_id
LIMIT 20;
