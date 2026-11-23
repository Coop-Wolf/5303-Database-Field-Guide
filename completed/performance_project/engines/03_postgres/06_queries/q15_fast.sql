-- Q15 /fast — Insert many purchases in one transaction
--
-- What it answers: Inserts every purchase in the request body, then commits once. Returns the new rows with status 201, or 503 if the database refuses any of them.
-- Route:           POST /purchases/fast   (params: JSON array body; every route also takes db=)
-- Pattern:         — (see 08_concurrency/)
-- Engine:          PostgreSQL
--
-- Think about it:
-- This is the same INSERT as Q15, run once per purchase but inside one
-- transaction with one commit. Compare purchases per second with Q15. What
-- does a COMMIT wait for, and how does synchronous_commit change that?
--
-- The route runs this with run_write_many(), inside one transaction.

INSERT INTO purchases
    (customer_id, card_id, product_id, department, amount, purchase_date)
VALUES (%(customer_id)s, %(card_id)s, %(product_id)s, %(department)s, %(amount)s, %(purchase_date)s)
RETURNING purchase_id, customer_id, product_id, department, amount, purchase_date;
