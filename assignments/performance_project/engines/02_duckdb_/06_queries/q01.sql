-- Q01 — One customer by id
--
-- What it answers: "Show me customer 42."
-- Route:           GET /customers   (params: customer_id; every route also takes db=)
-- Pattern:         plan basics (see 07_explain/)
-- Engine:          DuckDB
--
-- Think about it:
-- Run this in idx_1m with EXPLAIN, then with EXPLAIN ANALYZE. What scan type
-- does each one report for customers? Which should you believe, and why can
-- they disagree? Then compare the time with SQLite's: what is DuckDB paying
-- for that doesn't depend on the data at all?

SELECT c.customer_id, c.first_name, c.last_name, c.email, c.zipcode, z.state_code
FROM customers c
JOIN zipcodes z ON z.zipcode = c.zipcode
WHERE c.customer_id = $customer_id;
