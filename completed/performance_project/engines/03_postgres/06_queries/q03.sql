-- Q03 — Purchases in a date range
--
-- What it answers: "Show me the first 100 purchases from the first week of March 2025."
-- Route:           GET /purchases   (params: start, end; every route also takes db=)
-- Pattern:         plan basics (see 07_explain/)
-- Engine:          PostgreSQL
--
-- Think about it:
-- idx_* walks idx_purchases_date and feeds an Incremental Sort. noidx_* uses
-- a Parallel Seq Scan. How many processes worked on the noidx_* version (look
-- for "Workers Launched"), and why would the planner start them for a query
-- that returns 100 rows?

SELECT purchase_id, customer_id, product_id, department, amount, purchase_date
FROM purchases
WHERE purchase_date >= %(start)s AND purchase_date < %(end)s
ORDER BY purchase_date, purchase_id
LIMIT 100;
