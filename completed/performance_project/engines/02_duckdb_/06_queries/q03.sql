-- Q03 — Purchases in a date range
--
-- What it answers: "Show me the first 100 purchases from the first week of March 2025."
-- Route:           GET /purchases   (params: start, end; every route also takes db=)
-- Pattern:         plan basics (see 07_explain/)
-- Engine:          DuckDB
--
-- Think about it:
-- In SQLite, idx_* turned this into a range seek and noidx_* scanned.
-- Compare DuckDB's two plans: how many rows does each scan, and is there an
-- index scan anywhere? DuckDB can skip a row group when its min/max for
-- purchase_date can't match. Can it skip any here? (Find out how dates are
-- spread across purchase_id order.)

SELECT purchase_id, customer_id, product_id, department, amount, purchase_date
FROM purchases
WHERE purchase_date >= $start AND purchase_date < $end
ORDER BY purchase_date, purchase_id
LIMIT 100;
