-- Q04 — One customer's purchase history
--
-- What it answers: "Show me this customer's 100 most recent purchases, with product names."
-- Route:           GET /customers/purchases   (params: customer_id; every route also takes db=)
-- Pattern:         plan basics (see 07_explain/)
-- Engine:          PostgreSQL
--
-- Think about it:
-- The idx_* plan doesn't use idx_purchases_customer. Which index does it
-- use, in which direction, and how many rows did it read to find 100? Why is
-- that a good plan for "the 100 most recent", and when would it be a bad one?

SELECT pu.purchase_id, pu.purchase_date, pr.product_name, pu.department, pu.amount
FROM purchases pu
JOIN products pr ON pr.product_id = pu.product_id
WHERE pu.customer_id = %(customer_id)s
ORDER BY pu.purchase_date DESC, pu.purchase_id DESC
LIMIT 100;
