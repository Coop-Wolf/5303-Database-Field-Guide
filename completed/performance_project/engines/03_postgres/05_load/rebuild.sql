-- =============================================================================
-- rebuild.sql  --  Rebuild the classroom schema from scratch
-- =============================================================================
-- Run from engines/03_postgres/05_load/:
--
--     psql postgresql://student:student@localhost:5432/course -f rebuild.sql
--
-- 1. Drops and recreates the schema `classroom`, and makes it the default.
-- 2. schema.sql creates the tables and view; load_classroom.sql runs the ETL;
--    indexes.sql adds the secondary indexes.
-- 3. The checks at the end round-trip the row count and revenue.
--
-- Everything runs in ONE transaction: if any step fails, nothing changes,
-- including the DROP SCHEMA. (SQLite's rebuild can't promise that.)
-- No foreign-key check step: PostgreSQL checks every foreign key on insert.
-- =============================================================================

\set ON_ERROR_STOP on
BEGIN;

DROP SCHEMA IF EXISTS classroom CASCADE;
CREATE SCHEMA classroom;
SET search_path TO classroom;

\ir ../04_model/schema.sql
\ir load_classroom.sql
\ir indexes.sql

SELECT 'states' AS table_name, count(*) AS rows FROM states
UNION ALL SELECT 'zipcodes',    count(*) FROM zipcodes
UNION ALL SELECT 'card_types',  count(*) FROM card_types
UNION ALL SELECT 'departments', count(*) FROM departments
UNION ALL SELECT 'customers',   count(*) FROM customers
UNION ALL SELECT 'cards',       count(*) FROM cards
UNION ALL SELECT 'products',    count(*) FROM products
UNION ALL SELECT 'purchases',   count(*) FROM purchases;

SELECT '== verification ==' AS step;
SELECT count(*) AS purchases, sum(amount) AS revenue, count(DISTINCT purchase_id) AS ids
FROM purchases;

COMMIT;

-- fresh statistics, so the planner knows how big each table is
ANALYZE states, zipcodes, card_types, departments, customers, cards, products, purchases, monthly_sales;
SELECT '== rebuild complete ==' AS step;
