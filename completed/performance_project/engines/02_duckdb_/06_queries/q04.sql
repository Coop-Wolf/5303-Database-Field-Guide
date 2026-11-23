-- Q04 — One customer's purchase history
--
-- What it answers: "Show me this customer's 100 most recent purchases, with product names."
-- Route:           GET /customers/purchases   (params: customer_id; every route also takes db=)
-- Pattern:         plan basics (see 07_explain/)
-- Engine:          DuckDB
--
-- Think about it:
-- idx_* has an index on customer_id, and EXPLAIN ANALYZE shows DuckDB using
-- it. Is idx_* faster than noidx_*? Use the "scanned" count and the time on
-- each plan line to explain what you see.

SELECT pu.purchase_id, pu.purchase_date, pr.product_name, pu.department, pu.amount
FROM purchases pu
JOIN products pr ON pr.product_id = pu.product_id
WHERE pu.customer_id = $customer_id
ORDER BY pu.purchase_date DESC, pu.purchase_id DESC
LIMIT 100;
