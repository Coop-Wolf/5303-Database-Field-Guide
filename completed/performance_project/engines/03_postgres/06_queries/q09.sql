-- Q09 — Revenue by state
--
-- What it answers: "Total purchases and revenue for each state."
-- Route:           GET /stats/revenue_by_state   (params: —; every route also takes db=)
-- Pattern:         plan basics (see 07_explain/)
-- Engine:          PostgreSQL
--
-- Think about it:
-- SQLite's fastest version read the covering index idx_purchases_cust_amount.
-- PostgreSQL's idx_* plan ignores it. What does it do instead, with how many
-- processes? Run it again after SET max_parallel_workers_per_gather = 0 and
-- compare.

SELECT z.state_code, COUNT(*) AS num_purchases, ROUND(SUM(pu.amount), 2) AS revenue
FROM purchases pu
JOIN customers c ON c.customer_id = pu.customer_id
JOIN zipcodes  z ON z.zipcode     = c.zipcode
GROUP BY z.state_code
ORDER BY revenue DESC, z.state_code;
