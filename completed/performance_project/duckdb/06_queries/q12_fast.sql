-- Q12 (fast) — Random sample: `ORDER BY random()` vs. random ids
--
-- What it answers: "Give me 10 random purchases."
-- Route:           GET /purchases/sample/fast   (params: — (10 random ids chosen in Python: id1..id10); every route also takes db=)
-- Pattern:         random_sampling
-- Engine:          DuckDB
--
-- Think about it:
-- ORDER BY random() touches every row in any engine. DuckDB also has
-- sampling built in: try SELECT ... FROM purchases USING SAMPLE 10 ROWS. Is it
-- faster? Is it the same kind of random? (Look up reservoir vs. system
-- sampling.) What has to be true about purchase_id for the fast version's
-- sample to be fair?
--
-- The route picks 10 random ids in Python first:
--   max_id = SELECT MAX(purchase_id) FROM purchases
--   ids    = random.sample(range(1, max_id + 1), 10)  -> $id1 .. $id10

SELECT purchase_id, customer_id, product_id, amount, purchase_date
FROM purchases
WHERE purchase_id IN ($id1, $id2, $id3, $id4, $id5, $id6, $id7, $id8, $id9, $id10)
ORDER BY purchase_id;
