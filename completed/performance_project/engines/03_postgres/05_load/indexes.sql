-- =============================================================================
-- indexes.sql  --  The secondary indexes every idx_* database gets
-- =============================================================================
-- The same ten indexes as SQLite's idx_* files (its schema.sql plus
-- covering_indexes.sql), so the two engines are measured with the same help
-- (fairness rule 10). noidx_* skips this file and keeps only what PRIMARY KEY
-- and UNIQUE create.
--
-- The last three are SQLite's "covering" indexes, written the SQLite way: the
-- extra columns are part of the key. PostgreSQL can also write them as
-- (customer_id) INCLUDE (amount). 07_explain/ asks whether that matters.
-- =============================================================================

-- foreign keys and the date: PostgreSQL doesn't index foreign keys for you
CREATE INDEX idx_zipcodes_state       ON zipcodes (state_code);
CREATE INDEX idx_customers_zipcode    ON customers (zipcode);
CREATE INDEX idx_cards_customer       ON cards (customer_id);
CREATE INDEX idx_purchases_customer   ON purchases (customer_id);
CREATE INDEX idx_purchases_product    ON purchases (product_id);
CREATE INDEX idx_purchases_department ON purchases (department);
CREATE INDEX idx_purchases_date       ON purchases (purchase_date);

-- covering: every column a catalog query needs, so it can skip the table
CREATE INDEX idx_purchases_cust_amount      ON purchases (customer_id, amount);
CREATE INDEX idx_purchases_prod_amount      ON purchases (product_id, amount);
CREATE INDEX idx_purchases_date_cust_amount ON purchases (purchase_date, customer_id, amount);
