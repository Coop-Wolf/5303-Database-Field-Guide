-- Q13 (fast) — Revenue by month: scan vs. summary table
--
-- What it answers: "Total purchases and revenue for every month."
-- Route:           GET /stats/revenue_by_month/fast   (params: —; every route also takes db=)
-- Pattern:         counting_and_summaries
-- Engine:          PostgreSQL
--
-- Think about it:
-- All of history, no WHERE: every purchase is read. How is the work split
-- (Partial HashAggregate, Gather Merge, Finalize)? Compare Q13 and Q13 fast:
-- is the summary table worth more or less here than it was in SQLite?

SELECT month, SUM(num_purchases) AS num_purchases, ROUND(SUM(revenue), 2) AS revenue
FROM monthly_sales
GROUP BY month
ORDER BY month;
