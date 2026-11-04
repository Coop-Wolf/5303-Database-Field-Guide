-- =============================================================================
-- rebuild.sql  --  Rebuild the classroom DuckDB database from scratch
-- =============================================================================
-- Run from engines/02_duckdb/05_load/:
--
--     rm -f store_classroom.duckdb
--     duckdb store_classroom.duckdb ".read rebuild.sql"
--
-- 1. schema.sql drops and recreates every table, the sequence, and the view.
-- 2. load_classroom.sql runs the ETL from the CSV.
-- 3. The checks below round-trip the row count and revenue against the CSV.
--
-- No foreign-key check step: DuckDB enforces foreign keys on every insert,
-- so a load that finished can't have broken one.
-- =============================================================================

.read ../04_model/schema.sql
.read load_classroom.sql

SELECT '== verification ==' AS step;

SELECT (SELECT count(*)    FROM purchases) AS purchases,
       (SELECT sum(amount) FROM purchases) AS revenue,
       (SELECT count(*)    FROM read_csv('../../../datasets/store/classroom/store_flat.csv')) AS csv_rows,
       (SELECT round(sum(purchase_amount), 2)
          FROM read_csv('../../../datasets/store/classroom/store_flat.csv')) AS csv_revenue;

SELECT '== rebuild complete ==' AS step;
