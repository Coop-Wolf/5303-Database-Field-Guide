#!/usr/bin/env python3
"""
build_postgres.py -- build the PostgreSQL experiment schemas from the SQLite files.

    python3 datasets/store/generator/make_dbs.py         # first: the SQLite files
    python3 engines/03_postgres/05_load/build_postgres.py           # 10k, 100k, 1m
    python3 engines/03_postgres/05_load/build_postgres.py --sizes 10k
    python3 engines/03_postgres/05_load/build_postgres.py --writes  # scratch copy for 08

SQLite keeps each experiment database in its own file. PostgreSQL keeps them
as **schemas** inside one database, with the same names:

    idx_<size>     schema.sql + indexes.sql (the same ten indexes as SQLite)
    noidx_<size>   schema.sql only: PRIMARY KEY and UNIQUE, nothing else
    writes         a copy of idx_100k for 08_concurrency to write into

Each one reads idx_<size>.db with Python's sqlite3 and streams every table in
with COPY, so both engines hold exactly the same rows. Then it builds the
monthly_sales rollup, moves the purchase_id counter past the loaded rows,
and runs VACUUM ANALYZE (statistics for the planner, and the visibility map
that index-only scans need).

Connection: --dsn, else $DATABASE_URL, else the course default below.
Re-running is safe: each schema is dropped and rebuilt.

Needs: pip install "psycopg[binary]"
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import time
from pathlib import Path

import psycopg
from psycopg import sql

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SCHEMA = HERE.parent / "04_model" / "schema.sql"
INDEXES = HERE / "indexes.sql"
SQLITE_DIR = Path(os.environ.get("DATA_DIR", ROOT / "datasets" / "store" / "generated" / "sqlite")).expanduser()
DEFAULT_DSN = "postgresql://student:student@localhost:5432/course"
SIZES = ["10k", "100k", "1m", "practice"]

# Parent tables first, so foreign keys have something to point at.
TABLES = {
    "states":      ["state_code"],
    "card_types":  ["card_type"],
    "departments": ["department"],
    "zipcodes":    ["zipcode", "state_code"],
    "customers":   ["customer_id", "first_name", "last_name", "email", "address", "zipcode"],
    "cards":       ["card_id", "customer_id", "card_type", "card_number"],
    "products":    ["product_id", "product_name", "unit_price"],
    "purchases":   ["purchase_id", "customer_id", "card_id", "product_id",
                    "department", "amount", "purchase_date"],
}

SUMMARY = """
INSERT INTO monthly_sales
SELECT to_char(pu.purchase_date, 'YYYY-MM'), z.state_code, pu.department,
       count(*), sum(pu.amount)
FROM purchases pu
JOIN customers c ON c.customer_id = pu.customer_id
JOIN zipcodes  z ON z.zipcode     = c.zipcode
GROUP BY 1, 2, 3
"""


def build(dsn: str, schema: str, source: Path, with_indexes: bool) -> tuple[int, int, float]:
    t0 = time.perf_counter()
    src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    with psycopg.connect(dsn) as con:
        s = sql.Identifier(schema)
        con.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(s))
        con.execute(sql.SQL("CREATE SCHEMA {}").format(s))
        con.execute(sql.SQL("SET search_path TO {}").format(s))
        con.execute(SCHEMA.read_text())
        with con.cursor() as cur:
            for table, cols in TABLES.items():
                order = " ORDER BY purchase_id" if table == "purchases" else ""
                rows = src.execute(f"SELECT {', '.join(cols)} FROM {table}{order}")
                copy = sql.SQL("COPY {} ({}) FROM STDIN").format(
                    sql.Identifier(table), sql.SQL(", ").join(map(sql.Identifier, cols)))
                with cur.copy(copy) as cp:
                    for row in rows:
                        cp.write_row(row)
        con.execute(SUMMARY)
        if with_indexes:
            con.execute(INDEXES.read_text())
        con.execute("SELECT setval(pg_get_serial_sequence('purchases', 'purchase_id'), "
                    "(SELECT max(purchase_id) FROM purchases))")
        con.commit()
        con.autocommit = True                     # VACUUM can't run inside a transaction
        con.execute("VACUUM ANALYZE " + ", ".join([*TABLES, "monthly_sales"]))
        n = con.execute("SELECT count(*) FROM purchases").fetchone()[0]
        size = con.execute(
            "SELECT sum(pg_total_relation_size(c.oid))::bigint FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = %s AND c.relkind IN ('r', 'm')", (schema,)).fetchone()[0]
    src.close()
    return n, size, time.perf_counter() - t0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sizes", nargs="+", default=["10k", "100k", "1m"], choices=SIZES)
    p.add_argument("--writes", action="store_true",
                   help="only (re)build the scratch schema 'writes' from idx_100k.db")
    p.add_argument("--dsn", default=os.environ.get("DATABASE_URL", DEFAULT_DSN))
    a = p.parse_args(argv)

    jobs = ([("writes", "100k", True)] if a.writes else
            [(f"{v}_{s}", s, v == "idx") for s in a.sizes for v in ("idx", "noidx")])
    try:
        psycopg.connect(a.dsn).close()
    except psycopg.OperationalError as exc:
        raise SystemExit(f"Can't connect to {a.dsn}\n{exc}\nIs the server running? (see 02_install/)")

    for schema, size, with_indexes in jobs:
        source = SQLITE_DIR / f"idx_{size}.db"
        if not source.exists():
            raise SystemExit(f"{source} not found. Run datasets/store/generator/make_dbs.py first.")
        n, size_bytes, secs = build(a.dsn, schema, source, with_indexes)
        print(f"{schema:<12} {n:>10,} purchases  {size_bytes / 1e6:7.1f} MB  {secs:5.1f} s")


if __name__ == "__main__":
    main()
