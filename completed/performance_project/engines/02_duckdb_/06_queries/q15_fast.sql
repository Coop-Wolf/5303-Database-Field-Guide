-- Q15 /fast — Insert many purchases in one transaction
--
-- What it answers: Inserts every purchase in the request body, then commits once. Returns the new rows with status 201, or 503 if DuckDB can't write.
-- Route:           POST /purchases/fast   (params: JSON array body; every route also takes db=)
-- Pattern:         — (see 08_concurrency/)
-- Engine:          DuckDB
--
-- Think about it:
-- This is the same INSERT as Q15, run once per purchase but inside one
-- transaction with one commit. DuckDB is built to load data in bulk. What does
-- that predict about purchases per second here compared with Q15?
--
-- The route runs this with run_write_many(), inside one transaction.

INSERT INTO purchases
    (customer_id, card_id, product_id, department, amount, purchase_date)
VALUES ($customer_id, $card_id, $product_id, $department, $amount, $purchase_date)
RETURNING purchase_id, customer_id, product_id, department, amount, purchase_date;
