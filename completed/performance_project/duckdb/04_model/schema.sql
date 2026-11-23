-- =============================================================================
-- schema.sql  --  The store schema in DuckDB
-- =============================================================================
-- Same eight tables, same columns, same keys as ../../01_sqlite/04_model/schema.sql.
-- What changes is how DuckDB wants them declared:
--
--   * Real types. DATE for dates (SQLite stores ISO text), DECIMAL(10,2) for
--     money (SQLite has no exact decimal), VARCHAR for text.
--   * Keys are enforced with ART indexes, and DuckDB has no ON UPDATE /
--     ON DELETE CASCADE, so foreign keys are plain REFERENCES.
--   * No rowid alias: purchase_id gets its numbers from a SEQUENCE.
--   * No secondary indexes here. DuckDB's own indexes are for keys and point
--     lookups; it skips data with per-block min/max values instead. The idx_*
--     build adds SQLite's indexes anyway, so you can measure whether they help.
--
-- The noidx_* build uses the same columns with none of the constraints.
-- =============================================================================

DROP VIEW     IF EXISTS purchase_details;
DROP TABLE    IF EXISTS monthly_sales;
DROP TABLE    IF EXISTS purchases;
DROP TABLE    IF EXISTS cards;
DROP TABLE    IF EXISTS customers;
DROP TABLE    IF EXISTS zipcodes;
DROP TABLE    IF EXISTS states;
DROP TABLE    IF EXISTS card_types;
DROP TABLE    IF EXISTS departments;
DROP TABLE    IF EXISTS products;
DROP SEQUENCE IF EXISTS purchase_id_seq;

CREATE TABLE states (
    state_code  VARCHAR PRIMARY KEY
                CHECK (length(state_code) = 2 AND state_code = upper(state_code))
);

CREATE TABLE card_types  (card_type  VARCHAR PRIMARY KEY);
CREATE TABLE departments (department VARCHAR PRIMARY KEY);

CREATE TABLE zipcodes (
    zipcode     VARCHAR PRIMARY KEY,
    state_code  VARCHAR NOT NULL REFERENCES states(state_code)
);

CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY,
    first_name  VARCHAR NOT NULL,
    last_name   VARCHAR NOT NULL,
    email       VARCHAR NOT NULL UNIQUE,
    address     VARCHAR NOT NULL,
    zipcode     VARCHAR NOT NULL REFERENCES zipcodes(zipcode)
);

CREATE TABLE cards (
    card_id     INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
    card_type   VARCHAR NOT NULL REFERENCES card_types(card_type),
    card_number VARCHAR NOT NULL UNIQUE
);

CREATE TABLE products (
    product_id   INTEGER PRIMARY KEY,
    product_name VARCHAR NOT NULL UNIQUE,
    unit_price   DECIMAL(10, 2) NOT NULL CHECK (unit_price >= 0)
);

CREATE SEQUENCE purchase_id_seq;

CREATE TABLE purchases (
    purchase_id   INTEGER PRIMARY KEY DEFAULT nextval('purchase_id_seq'),
    customer_id   INTEGER NOT NULL REFERENCES customers(customer_id),
    card_id       INTEGER NOT NULL REFERENCES cards(card_id),
    product_id    INTEGER NOT NULL REFERENCES products(product_id),
    department    VARCHAR NOT NULL REFERENCES departments(department),
    amount        DECIMAL(10, 2) NOT NULL CHECK (amount >= 0),
    purchase_date DATE NOT NULL
);

CREATE VIEW purchase_details AS
SELECT pu.purchase_id, pu.purchase_date, c.customer_id,
       c.first_name || ' ' || c.last_name AS customer_name,
       c.email, c.address, c.zipcode, z.state_code,
       pr.product_name, pu.department, pu.amount, ct.card_type
FROM purchases  pu
JOIN customers  c  ON c.customer_id = pu.customer_id
JOIN zipcodes   z  ON z.zipcode     = c.zipcode
JOIN products   pr ON pr.product_id = pu.product_id
JOIN cards      cd ON cd.card_id    = pu.card_id
JOIN card_types ct ON ct.card_type  = cd.card_type;
