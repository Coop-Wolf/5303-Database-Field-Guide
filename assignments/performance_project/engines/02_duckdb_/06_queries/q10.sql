-- Q10 — Top 10 products by revenue
--
-- What it answers: "Which 10 products brought in the most money?"
-- Route:           GET /products/top   (params: —; every route also takes db=)
-- Pattern:         plan basics (see 07_explain/)
-- Engine:          DuckDB
--
-- Think about it:
-- SQLite accepted GROUP BY pr.product_id alone. DuckDB needs product_name in
-- the GROUP BY too. Why does it refuse, and why does PostgreSQL accept the
-- short form? LIMIT 10 still doesn't make this cheap. Why not?

SELECT pr.product_id, pr.product_name,
       COUNT(*) AS num_purchases, ROUND(SUM(pu.amount), 2) AS revenue
FROM purchases pu
JOIN products pr ON pr.product_id = pu.product_id
GROUP BY pr.product_id, pr.product_name   -- DuckDB requires every non-aggregated column here
ORDER BY revenue DESC, pr.product_id
LIMIT 10;
