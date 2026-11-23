-- Q10 — Top 10 products by revenue
--
-- What it answers: "Which 10 products brought in the most money?"
-- Route:           GET /products/top   (params: —; every route also takes db=)
-- Pattern:         plan basics (see 07_explain/)
-- Engine:          PostgreSQL
--
-- Think about it:
-- This is SQLite's version: GROUP BY pr.product_id, with product_name in the
-- SELECT. DuckDB refused it. Why does PostgreSQL accept it? LIMIT 10 still
-- doesn't make the query cheap. Why not?

SELECT pr.product_id, pr.product_name,
       COUNT(*) AS num_purchases, ROUND(SUM(pu.amount), 2) AS revenue
FROM purchases pu
JOIN products pr ON pr.product_id = pu.product_id
GROUP BY pr.product_id
ORDER BY revenue DESC, pr.product_id
LIMIT 10;
