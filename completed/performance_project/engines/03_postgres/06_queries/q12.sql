-- Q12 — Random sample: `ORDER BY random()` vs. random ids
--
-- What it answers: "Give me 10 random purchases."
-- Route:           GET /purchases/sample   (params: —; every route also takes db=)
-- Pattern:         random_sampling
-- Engine:          PostgreSQL
--
-- Think about it:
-- ORDER BY random() reads every row, then keeps 10 (top-N heapsort).
-- PostgreSQL also has TABLESAMPLE: try ... FROM purchases TABLESAMPLE SYSTEM (0.01)
-- and TABLESAMPLE BERNOULLI (0.01). Is either the same kind of random as this?
-- What has to be true about purchase_id for the fast version to be fair?

SELECT purchase_id, customer_id, product_id, amount, purchase_date
FROM purchases
ORDER BY random()
LIMIT 10;
