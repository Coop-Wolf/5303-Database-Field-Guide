-- Q12 — Random sample: `ORDER BY random()` vs. random ids
--
-- What it answers: "Give me 10 random purchases."
-- Route:           GET /purchases/sample   (params: —; every route also takes db=)
-- Pattern:         random_sampling
-- Engine:          DuckDB
--
-- Think about it:
-- ORDER BY random() touches every row in any engine. DuckDB also has
-- sampling built in: try SELECT ... FROM purchases USING SAMPLE 10 ROWS. Is it
-- faster? Is it the same kind of random? (Look up reservoir vs. system
-- sampling.) What has to be true about purchase_id for the fast version's
-- sample to be fair?

SELECT purchase_id, customer_id, product_id, amount, purchase_date
FROM purchases
ORDER BY random()
LIMIT 10;
