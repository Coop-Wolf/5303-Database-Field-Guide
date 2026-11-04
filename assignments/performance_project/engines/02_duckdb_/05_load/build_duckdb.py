#!/usr/bin/env python3
"""
build_duckdb.py -- build the DuckDB experiment databases from the SQLite ones.

    python3 datasets/store/generator/make_dbs.py       # first: the SQLite files
    python3 engines/02_duckdb/05_load/build_duckdb.py    # then: 10k, 100k, 1m
    python3 engines/02_duckdb/05_load/build_duckdb.py --sizes 10k

For each size it reads idx_<size>.db through DuckDB's sqlite extension, so
both engines hold exactly the same rows, and writes two files:

    idx_<size>.duckdb     schema.sql: keys, constraints, plus SQLite's indexes
    noidx_<size>.duckdb   the same columns and rows, no constraints, no indexes

Both get the monthly_sales summary table and the purchase_details view.

Where the files go: $DUCKDB_DIR if set; otherwise a "duckdb" folder next to
the SQLite files ($DATA_DIR, or datasets/store/generated/sqlite).

Needs: pip install duckdb
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

import duckdb

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SCHEMA = HERE.parent / "04_model" / "schema.sql"
SQLITE_DIR = Path(os.environ.get("DATA_DIR", ROOT / "datasets" / "store" / "generated" / "sqlite")).expanduser()
DUCKDB_DIR = Path(os.environ.get("DUCKDB_DIR", SQLITE_DIR.parent / "duckdb")).expanduser()
SIZES = ["10k", "100k", "1m", "practice"]

# Parent tables first, so foreign keys have something to point at.
TABLES = {
    "states":      "SELECT state_code FROM s.states",
    "card_types":  "SELECT card_type FROM s.card_types",
    "departments": "SELECT department FROM s.departments",
    "zipcodes":    "SELECT zipcode, state_code FROM s.zipcodes",
    "customers":   """SELECT CAST(customer_id AS INTEGER) AS customer_id, first_name, last_name,
                             email, address, zipcode FROM s.customers""",
    "cards":       """SELECT CAST(card_id AS INTEGER) AS card_id, CAST(customer_id AS INTEGER) AS customer_id,
                             card_type, card_number FROM s.cards""",
    "products":    """SELECT CAST(product_id AS INTEGER) AS product_id, product_name,
                             CAST(unit_price AS DECIMAL(10,2)) AS unit_price FROM s.products""",
    "purchases":   """SELECT CAST(purchase_id AS INTEGER) AS purchase_id, CAST(customer_id AS INTEGER) AS customer_id,
                             CAST(card_id AS INTEGER) AS card_id, CAST(product_id AS INTEGER) AS product_id,
                             department, CAST(amount AS DECIMAL(10,2)) AS amount,
                             CAST(purchase_date AS DATE) AS purchase_date
                      FROM s.purchases ORDER BY purchase_id""",
}

# The same secondary indexes SQLite's idx_* files have (schema + covering_indexes.sql).
SQLITE_INDEXES = [
    "CREATE INDEX idx_zipcodes_state ON zipcodes(state_code)",
    "CREATE INDEX idx_customers_zipcode ON customers(zipcode)",
    "CREATE INDEX idx_cards_customer ON cards(customer_id)",
    "CREATE INDEX idx_purchases_customer ON purchases(customer_id)",
    "CREATE INDEX idx_purchases_product ON purchases(product_id)",
    "CREATE INDEX idx_purchases_department ON purchases(department)",
    "CREATE INDEX idx_purchases_date ON purchases(purchase_date)",
    "CREATE INDEX idx_purchases_cust_amount ON purchases(customer_id, amount)",
    "CREATE INDEX idx_purchases_prod_amount ON purchases(product_id, amount)",
    "CREATE INDEX idx_purchases_date_cust_amount ON purchases(purchase_date, customer_id, amount)",
]

SUMMARY = """
CREATE TABLE monthly_sales AS
SELECT strftime(pu.purchase_date, '%Y-%m') AS month, z.state_code, pu.department,
       COUNT(*) AS num_purchases, SUM(pu.amount) AS revenue
FROM purchases pu
JOIN customers c ON c.customer_id = pu.customer_id
JOIN zipcodes  z ON z.zipcode     = c.zipcode
GROUP BY ALL
"""


def connect_with_source(path: Path, source: Path) -> duckdb.DuckDBPyConnection:
    path.unlink(missing_ok=True)
    Path(str(path) + ".wal").unlink(missing_ok=True)
    con = duckdb.connect(str(path))
    con.execute("INSTALL sqlite; LOAD sqlite;")
    con.execute(f"ATTACH '{source}' AS s (TYPE sqlite, READ_ONLY)")
    return con


def view_sql() -> str:
    schema = SCHEMA.read_text()
    return schema[schema.index("CREATE VIEW purchase_details"):]


def build_idx(path: Path, source: Path) -> None:
    con = connect_with_source(path, source)
    next_id = con.execute("SELECT coalesce(max(purchase_id), 0) + 1 FROM s.purchases").fetchone()[0]
    schema = SCHEMA.read_text().replace(
        "CREATE SEQUENCE purchase_id_seq;", f"CREATE SEQUENCE purchase_id_seq START {next_id};")
    con.execute(schema)
    for table, select in TABLES.items():
        con.execute(f"INSERT INTO {table} {select}")
    for ddl in SQLITE_INDEXES:
        con.execute(ddl)
    con.execute(SUMMARY)
    con.execute("DETACH s")
    con.execute("CHECKPOINT")
    con.close()


def build_noidx(path: Path, source: Path) -> None:
    con = connect_with_source(path, source)
    for table, select in TABLES.items():
        # CREATE TABLE AS keeps the column names and types, and no constraints
        con.execute(f"CREATE TABLE {table} AS {select}")
    con.execute(SUMMARY)
    con.execute(view_sql())
    con.execute("DETACH s")
    con.execute("CHECKPOINT")
    con.close()


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sizes", nargs="+", default=["10k", "100k", "1m"], choices=SIZES)
    a = p.parse_args(argv)

    DUCKDB_DIR.mkdir(parents=True, exist_ok=True)
    for size in a.sizes:
        source = SQLITE_DIR / f"idx_{size}.db"
        if not source.exists():
            raise SystemExit(f"{source} not found. Run datasets/store/generator/make_dbs.py first.")
        for variant, build in (("idx", build_idx), ("noidx", build_noidx)):
            out = DUCKDB_DIR / f"{variant}_{size}.duckdb"
            t0 = time.perf_counter()
            build(out, source)
            con = duckdb.connect(str(out), read_only=True)
            n = con.execute("SELECT count(*) FROM purchases").fetchone()[0]
            con.close()
            mb = out.stat().st_size / 1e6
            print(f"{out.name:<20} {n:>10,} purchases  {mb:7.1f} MB  {time.perf_counter() - t0:5.1f} s")
    print(f"\nwrote to {DUCKDB_DIR}")


if __name__ == "__main__":
    main()
