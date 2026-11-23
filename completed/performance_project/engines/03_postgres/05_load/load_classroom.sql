-- =============================================================================
-- load_classroom.sql  --  The 1,000-row classroom CSV into the store schema
-- =============================================================================
-- Run through rebuild.sql, from engines/03_postgres/05_load/ (the \copy path
-- below is relative to where you started psql).
--
-- Same plan as SQLite's load_classroom.sql: stage the raw file as text, fill
-- parents first, look up ids by natural key on the way into purchases.
-- What's different:
--
--   * \copy, not .import. It's a psql command: psql reads the file on YOUR
--     machine and streams it to the server. (Plain COPY ... FROM 'file' would
--     look for the file on the server, inside the container.)
--   * The staging table is TEMP: it lives only for this session and
--     disappears on its own. No DROP needed.
--   * Dates convert with to_date(..., 'MM/DD/YYYY'). A bare '3/9/2026'::date
--     also works, but only because the server's DateStyle happens to be MDY.
--     On a DMY server it would quietly mean 3 September. Say the format.
-- =============================================================================

CREATE TEMP TABLE staging_raw (
    id text, first_name text, last_name text, email text, cc_type text,
    cc_number text, purchase_dept text, purchase_amount text, address text,
    zipcode text, state text, prod_name text, purchase_data text
);

\copy staging_raw FROM '../../../datasets/store/classroom/store_flat.csv' WITH (FORMAT csv, HEADER true)

SELECT 'staging_raw rows loaded: ' || count(*) AS step FROM staging_raw;

-- Parents first, so the children's foreign keys have something to point at.
INSERT INTO states      SELECT DISTINCT state          FROM staging_raw ORDER BY 1;
INSERT INTO card_types  SELECT DISTINCT cc_type        FROM staging_raw ORDER BY 1;
INSERT INTO departments SELECT DISTINCT purchase_dept  FROM staging_raw ORDER BY 1;
INSERT INTO zipcodes    SELECT DISTINCT zipcode, state FROM staging_raw;

INSERT INTO customers (customer_id, first_name, last_name, email, address, zipcode)
SELECT id::integer, first_name, last_name, email, address, zipcode FROM staging_raw;

INSERT INTO cards (card_id, customer_id, card_type, card_number)
SELECT id::integer, id::integer, cc_type, cc_number FROM staging_raw;

INSERT INTO products (product_id, product_name, unit_price)
SELECT row_number() OVER (ORDER BY prod_name), prod_name, max(purchase_amount::numeric)
FROM staging_raw
GROUP BY prod_name;

-- The source's date column is named purchase_data (a typo in the CSV).
INSERT INTO purchases (purchase_id, customer_id, card_id, product_id, department, amount, purchase_date)
SELECT s.id::integer, c.customer_id, cd.card_id, pr.product_id, s.purchase_dept,
       s.purchase_amount::numeric, to_date(s.purchase_data, 'MM/DD/YYYY')
FROM staging_raw s
JOIN customers c  ON c.email         = s.email
JOIN cards     cd ON cd.card_number  = s.cc_number
JOIN products  pr ON pr.product_name = s.prod_name;

-- The identity counter starts at 1; move it past the loaded ids so new
-- purchases (Q15) don't collide. (DuckDB had no setval(); PostgreSQL does.)
SELECT setval(pg_get_serial_sequence('purchases', 'purchase_id'),
              (SELECT max(purchase_id) FROM purchases)) AS next_id_after;

INSERT INTO monthly_sales
SELECT to_char(pu.purchase_date, 'YYYY-MM'), z.state_code, pu.department,
       count(*), sum(pu.amount)
FROM purchases pu
JOIN customers c ON c.customer_id = pu.customer_id
JOIN zipcodes  z ON z.zipcode     = c.zipcode
GROUP BY 1, 2, 3;
