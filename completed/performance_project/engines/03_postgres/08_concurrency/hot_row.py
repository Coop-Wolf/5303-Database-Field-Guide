#!/usr/bin/env python3
"""
hot_row.py -- many clients sell the same product at once. Does every sale count?

One row, `writes.stock`, holds how many units of product 1 are on hand. Each
worker thread opens its own connection and sells one unit at a time, over
and over. Every strategy starts from the same stock and makes the same number
of sales, so the final on_hand should be exactly 0. Anything else is a sale
the database lost track of.

    python3 hot_row.py                         # all four strategies
    python3 hot_row.py --strategy naive        # just one
    python3 hot_row.py --workers 16 --sales 100

The four ways to sell one unit:

    naive            SELECT on_hand; compute on_hand - 1 in Python; UPDATE ... SET on_hand = <that>
    atomic           UPDATE ... SET on_hand = on_hand - 1     (one statement)
    for_update       SELECT ... FOR UPDATE; then UPDATE        (lock the row first)
    repeatable_read  naive, but in a REPEATABLE READ transaction, retried when
                     PostgreSQL refuses it

Writes only to the `writes` schema (build it with build_postgres.py --writes).
Connection: --dsn, else $DATABASE_URL, else the course default.

Needs: pip install "psycopg[binary]"
"""

from __future__ import annotations

import argparse
import os
import threading
import time

import psycopg
from psycopg import errors

DEFAULT_DSN = "postgresql://student:student@localhost:5432/course"
STRATEGIES = ["naive", "atomic", "for_update", "repeatable_read"]


def reset(dsn: str, units: int) -> None:
    with psycopg.connect(dsn, autocommit=True) as con:
        if not con.execute("SELECT 1 FROM pg_namespace WHERE nspname = 'writes'").fetchone():
            raise SystemExit("Schema writes not found. Run build_postgres.py --writes first.")
        con.execute("CREATE TABLE IF NOT EXISTS writes.stock "
                    "(product_id integer PRIMARY KEY, on_hand integer NOT NULL)")
        con.execute("DELETE FROM writes.stock")
        con.execute("INSERT INTO writes.stock VALUES (1, %s)", (units,))


def sell_one(con: psycopg.Connection, strategy: str, seen: list[str]) -> int:
    """Sell one unit. Returns how many times it had to retry; keeps the first error text."""
    retries = 0
    while True:
        try:
            if strategy == "atomic":
                with con.transaction():
                    con.execute("UPDATE writes.stock SET on_hand = on_hand - 1 WHERE product_id = 1")
            elif strategy == "naive":
                with con.transaction():
                    (n,) = con.execute("SELECT on_hand FROM writes.stock WHERE product_id = 1").fetchone()
                    con.execute("UPDATE writes.stock SET on_hand = %s WHERE product_id = 1", (n - 1,))
            elif strategy == "for_update":
                with con.transaction():
                    (n,) = con.execute("SELECT on_hand FROM writes.stock WHERE product_id = 1 "
                                       "FOR UPDATE").fetchone()
                    con.execute("UPDATE writes.stock SET on_hand = %s WHERE product_id = 1", (n - 1,))
            elif strategy == "repeatable_read":
                with con.transaction():
                    con.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
                    (n,) = con.execute("SELECT on_hand FROM writes.stock WHERE product_id = 1").fetchone()
                    con.execute("UPDATE writes.stock SET on_hand = %s WHERE product_id = 1", (n - 1,))
            return retries
        except errors.SerializationFailure as exc:
            if not seen:
                seen.append(str(exc).splitlines()[0])
            retries += 1                              # someone else changed the row first: try again


def run(dsn: str, strategy: str, workers: int, sales: int) -> dict:
    units = workers * sales
    reset(dsn, units)
    retries = [0] * workers
    first_error: list[str] = []
    start = threading.Barrier(workers + 1)

    def worker(i: int) -> None:
        with psycopg.connect(dsn, autocommit=True) as con:
            start.wait()
            for _ in range(sales):
                retries[i] += sell_one(con, strategy, first_error)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(workers)]
    for t in threads:
        t.start()
    start.wait()
    t0 = time.perf_counter()
    for t in threads:
        t.join()
    seconds = time.perf_counter() - t0

    with psycopg.connect(dsn) as con:
        (left,) = con.execute("SELECT on_hand FROM writes.stock WHERE product_id = 1").fetchone()
    return {"strategy": strategy, "sales": units, "on_hand_after": left,
            "retries": sum(retries), "seconds": seconds, "sales_per_sec": units / seconds,
            "error": first_error[0] if first_error else ""}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--strategy", choices=STRATEGIES, nargs="+", default=STRATEGIES)
    p.add_argument("--workers", type=int, default=8, help="threads, each with its own connection")
    p.add_argument("--sales", type=int, default=200, help="units each worker sells")
    p.add_argument("--dsn", default=os.environ.get("DATABASE_URL", DEFAULT_DSN))
    a = p.parse_args(argv)

    print(f"{a.workers} workers x {a.sales} sales = {a.workers * a.sales} units, all from one row\n")
    print(f"{'strategy':<16} {'on_hand after':>13} {'retries':>8} {'seconds':>8} {'sales/sec':>10}")
    errors_seen: list[str] = []
    for s in a.strategy:
        r = run(a.dsn, s, a.workers, a.sales)
        print(f"{r['strategy']:<16} {r['on_hand_after']:>13,} {r['retries']:>8,} "
              f"{r['seconds']:>8.2f} {r['sales_per_sec']:>10,.0f}")
        if r["error"]:
            errors_seen.append(f"{s}: {r['error']}")
    print("\non_hand after should be 0. Anything above 0 is sales the database lost.")
    for e in errors_seen:
        print("first error retried --", e)


if __name__ == "__main__":
    main()
