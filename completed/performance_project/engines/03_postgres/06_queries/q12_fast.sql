-- Q12 (fast) — Random sample: `ORDER BY random()` vs. random ids
--
-- What it answers: "Give me 10 random purchases."
-- Route:           GET /purchases/sample/fast   (params: — (10 random ids chosen in Python: id1..id10); every route also takes db=)
-- Pattern:         random_sampling
-- Engine:          PostgreSQL
--
-- Think about it:
-- ORDER BY random() reads every row, then keeps 10 (top-N heapsort).
-- PostgreSQL also has TABLESAMPLE: try ... FROM purchases TABLESAMPLE SYSTEM (0.01)
-- and TABLESAMPLE BERNOULLI (0.01). Is either the same kind of random as this?
-- What has to be true about purchase_id for the fast version to be fair?
--
-- The route picks 10 random ids in Python first:
--   max_id = SELECT MAX(purchase_id) FROM purchases
--   ids    = random.sample(range(1, max_id + 1), 10)  -> :id1 .. :id10

SELECT purchase_id, customer_id, product_id, amount, purchase_date
FROM purchases
WHERE purchase_id IN (%(id1)s, %(id2)s, %(id3)s, %(id4)s, %(id5)s, %(id6)s, %(id7)s, %(id8)s, %(id9)s, %(id10)s)
ORDER BY purchase_id;
