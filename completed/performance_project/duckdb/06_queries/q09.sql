-- Q09 — Revenue by state
--
-- What it answers: "Total purchases and revenue for each state."
-- Route:           GET /stats/revenue_by_state   (params: —; every route also takes db=)
-- Pattern:         plan basics (see 07_explain/)
-- Engine:          DuckDB
--
-- Think about it:
-- No WHERE, so every engine must read every purchase. SQLite's best version
-- used an index so it read less of each row. How much of each purchase does
-- DuckDB read here: which columns, out of how many?

SELECT z.state_code, COUNT(*) AS num_purchases, ROUND(SUM(pu.amount), 2) AS revenue
FROM purchases pu
JOIN customers c ON c.customer_id = pu.customer_id
JOIN zipcodes  z ON z.zipcode     = c.zipcode
GROUP BY z.state_code
ORDER BY revenue DESC, z.state_code;
