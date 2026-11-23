#!/usr/bin/env python3
"""
commit_cost.py -- what does a COMMIT cost, and what does synchronous_commit buy?

Inserts purchases straight into the `writes` schema, with no API in between,
so the numbers are the database's own:

    python3 commit_cost.py                    # the full grid below
    python3 commit_cost.py --inserts 2000     # more per thread, steadier numbers

For each combination of

    synchronous_commit   on  (COMMIT waits until the WAL is on disk)
                         off (COMMIT returns at once; the WAL is flushed a moment later)
    threads              1, 8 (each with its own connection)
    rows per commit      1 (every INSERT its own transaction), 25 (one COMMIT per 25)

it reports commits per second and rows per second.

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

DEFAULT_DSN = "postgresql://student:student@localhost:5432/course"
INSERT = ("INSERT INTO writes.purchases "
          "(customer_id, card_id, product_id, department, amount, purchase_date) "
          "VALUES (1, 1, 1, 'Games', 9.99, '2026-01-15')")


def run(dsn: str, sync: str, threads: int, per_commit: int, inserts: int) -> tuple[float, float]:
    start = threading.Barrier(threads + 1)

    def worker() -> None:
        with psycopg.connect(dsn, autocommit=True) as con:
            con.execute(f"SET synchronous_commit = {sync}")
            start.wait()
            for _ in range(inserts // per_commit):
                with con.transaction():
                    for _ in range(per_commit):
                        con.execute(INSERT)

    ts = [threading.Thread(target=worker) for _ in range(threads)]
    for t in ts:
        t.start()
    start.wait()
    t0 = time.perf_counter()
    for t in ts:
        t.join()
    secs = time.perf_counter() - t0
    rows = threads * (inserts // per_commit) * per_commit
    return rows / per_commit / secs, rows / secs


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--inserts", type=int, default=1000, help="rows each thread inserts (default 1000)")
    p.add_argument("--dsn", default=os.environ.get("DATABASE_URL", DEFAULT_DSN))
    a = p.parse_args(argv)

    with psycopg.connect(a.dsn) as con:
        if not con.execute("SELECT 1 FROM pg_namespace WHERE nspname = 'writes'").fetchone():
            raise SystemExit("Schema writes not found. Run build_postgres.py --writes first.")

    print(f"{'synchronous_commit':<19} {'threads':>7} {'rows/commit':>11} {'commits/sec':>12} {'rows/sec':>10}")
    for per_commit in (1, 25):
        for threads in (1, 8):
            for sync in ("on", "off"):
                commits, rows = run(a.dsn, sync, threads, per_commit, a.inserts)
                print(f"{sync:<19} {threads:>7} {per_commit:>11} {commits:>12,.0f} {rows:>10,.0f}")


if __name__ == "__main__":
    main()
