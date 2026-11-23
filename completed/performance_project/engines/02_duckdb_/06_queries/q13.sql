-- Q13 — Revenue by month: scan vs. summary table
--
-- What it answers: "Total purchases and revenue for every month."
-- Route:           GET /stats/revenue_by_month   (params: —; every route also takes db=)
-- Pattern:         counting_and_summaries
-- Engine:          DuckDB
--
-- Think about it:
-- In SQLite, the summary table was the fix for this query. Compare Q13 and
-- Q13 fast here. Is monthly_sales still worth what it costs to keep fresh
-- (Section 8 of the SQLite unit)? What would have to change about the data
-- for your answer to flip?

SELECT strftime(purchase_date, '%Y-%m') AS month,
       COUNT(*) AS num_purchases, ROUND(SUM(amount), 2) AS revenue
FROM purchases
GROUP BY month
ORDER BY month;
