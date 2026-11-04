-- =============================================================================
-- load_classroom.sql  --  The 1,000-row classroom CSV into the store schema, in DuckDB
-- =============================================================================
-- Run from engines/02_duckdb/05_load/:
--
--     duckdb store_classroom.duckdb ".read ../04_model/schema.sql" ".read load_classroom.sql"
--
-- Same plan as SQLite's load_classroom.sql: stage the raw file, fill parents
-- first, look up ids on the way into purchases. Two steps disappear:
--
--   * No CREATE TABLE + .import. read_csv() reads the file in place and
--     guesses ("sniffs") every column's type.
--   * No date parsing CTE. The sniffer recognizes M/D/YYYY and hands back a
--     real DATE.
--
-- Read what it guessed before trusting it:   DESCRIBE staging_raw;
-- =============================================================================

CREATE OR REPLACE TEMP TABLE staging_raw AS
SELECT * FROM read_csv('../../../datasets/store/classroom/store_flat.csv');

SELECT 'staging_raw rows loaded: ' || count(*) FROM staging_raw;

-- Parents first, so the children's foreign keys have something to point at.
INSERT INTO states      SELECT DISTINCT state         FROM staging_raw ORDER BY 1;
INSERT INTO card_types  SELECT DISTINCT cc_type       FROM staging_raw ORDER BY 1;
INSERT INTO departments SELECT DISTINCT purchase_dept FROM staging_raw ORDER BY 1;
INSERT INTO zipcodes    SELECT DISTINCT zipcode, state FROM staging_raw;

INSERT INTO customers (customer_id, first_name, last_name, email, address, zipcode)
SELECT id, first_name, last_name, email, address, zipcode FROM staging_raw;

INSERT INTO cards (card_id, customer_id, card_type, card_number)
SELECT id, id, cc_type, cc_number FROM staging_raw;

INSERT INTO products (product_id, product_name, unit_price)
SELECT row_number() OVER (ORDER BY prod_name), prod_name, max(purchase_amount)
FROM staging_raw
GROUP BY prod_name;

-- The source's date column is named purchase_data (a typo in the CSV).
INSERT INTO purchases (purchase_id, customer_id, card_id, product_id, department, amount, purchase_date)
SELECT s.id, c.customer_id, cd.card_id, pr.product_id, s.purchase_dept,
       s.purchase_amount, s.purchase_data
FROM staging_raw s
JOIN customers c  ON c.email         = s.email
JOIN cards     cd ON cd.card_number  = s.cc_number
JOIN products  pr ON pr.product_name = s.prod_name;

DROP TABLE staging_raw;

-- The schema's sequence starts at 1; move it past the loaded ids so new
-- purchases (Q15) don't collide. DuckDB has no setval(), and won't drop a
-- sequence a column default still uses, so draw (and discard) one value per
-- loaded id instead.
SELECT count(nextval('purchase_id_seq')) AS ids_skipped
FROM range((SELECT max(purchase_id) FROM purchases));

SELECT 'states' AS table_name, count(*) AS rows FROM states
UNION ALL SELECT 'zipcodes',    count(*) FROM zipcodes
UNION ALL SELECT 'card_types',  count(*) FROM card_types
UNION ALL SELECT 'departments', count(*) FROM departments
UNION ALL SELECT 'customers',   count(*) FROM customers
UNION ALL SELECT 'cards',       count(*) FROM cards
UNION ALL SELECT 'products',    count(*) FROM products
UNION ALL SELECT 'purchases',   count(*) FROM purchases;
