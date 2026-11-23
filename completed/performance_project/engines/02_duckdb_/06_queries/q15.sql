-- Q15 — Insert a purchase
--
-- What it answers: Inserts one purchase inside a transaction and returns the new row with status 201. If DuckDB can't write (another process holds the file, or a transaction conflicts), it returns 503.
-- Route:           POST /purchases   (params: JSON body; every route also takes db=)
-- Pattern:         — (see 08_concurrency/)
-- Engine:          DuckDB
--
-- Think about it:
-- One process at a time may open a DuckDB file for writing; inside that
-- process, transactions don't wait for each other. What happens to the API's
-- writes with one worker process? With four? Section 8 is where you find out.
--
-- The route runs this with run_write(), inside a transaction.

INSERT INTO purchases
    (customer_id, card_id, product_id, department, amount, purchase_date)
VALUES ($customer_id, $card_id, $product_id, $department, $amount, $purchase_date)
RETURNING purchase_id, customer_id, product_id, department, amount, purchase_date;
