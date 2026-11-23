-- Q15 — Insert a purchase
--
-- What it answers: Inserts one purchase inside a transaction and returns the new row with status 201. If the database refuses the write (a constraint, a deadlock), it returns 503.
-- Route:           POST /purchases   (params: JSON body; every route also takes db=)
-- Pattern:         — (see 08_concurrency/)
-- Engine:          PostgreSQL
--
-- Think about it:
-- There's no file lock and no busy_timeout here: every connection can write.
-- What happens when four worker processes insert at once? And when many
-- clients update the SAME row? Section 8 measures both.
--
-- The route runs this with run_write(), inside a transaction.

INSERT INTO purchases
    (customer_id, card_id, product_id, department, amount, purchase_date)
VALUES (%(customer_id)s, %(card_id)s, %(product_id)s, %(department)s, %(amount)s, %(purchase_date)s)
RETURNING purchase_id, customer_id, product_id, department, amount, purchase_date;
