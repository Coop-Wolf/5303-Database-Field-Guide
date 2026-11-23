#!/usr/bin/env python3
"""
run_query.py -- run one catalog query by hand, with its %(name)s parameters bound.

psql can't bind psycopg-style %(name)s placeholders, so this does it for you.
From engines/03_postgres/06_queries/:

    python3 run_query.py q01.sql customer_id=7                        # schema classroom
    python3 run_query.py q03.sql start=2025-03-01 end=2025-03-08 --db idx_1m
    python3 run_query.py q04.sql customer_id=20912 --db idx_1m --analyze
    python3 run_query.py q09.sql --db idx_1m --runs 5 --workers 0

--db names the schema (idx_1m, noidx_10k, classroom, ...). --explain prints the
plan PostgreSQL chose; --analyze runs the query and prints the plan with real
row counts, times, and pages read (EXPLAIN (ANALYZE, BUFFERS)). --runs N runs it
N times and reports the median. --workers sets max_parallel_workers_per_gather
(0 turns parallel query off).

Connection: --dsn, else $DATABASE_URL, else the course default.
Needs: pip install "psycopg[binary]"
"""

from __future__ import annotations

import argparse
import os
import statistics
import time
from pathlib import Path

import psycopg
from psycopg import sql as pgsql

HERE = Path(__file__).resolve().parent
DEFAULT_DSN = "postgresql://student:student@localhost:5432/course"


def value(text: str):
    """'7' -> 7, '9.99' -> 9.99, anything else stays text (dates included)."""
    for cast in (int, float):
        try:
            return cast(text)
        except ValueError:
            pass
    return text


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("sql_file", type=Path)
    p.add_argument("params", nargs="*", help="name=value for each %%(name)s in the query")
    p.add_argument("--db", default="classroom", help="schema to run in (default: classroom)")
    p.add_argument("--dsn", default=os.environ.get("DATABASE_URL", DEFAULT_DSN))
    p.add_argument("--runs", type=int, default=1, help="run it N times and report the median time")
    p.add_argument("--workers", type=int, help="max_parallel_workers_per_gather (0 = no parallel query)")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--explain", action="store_true", help="show the plan instead of the rows")
    mode.add_argument("--analyze", action="store_true", help="run it and show the plan with actual rows and times")
    a = p.parse_args(argv)

    params = {k: value(v) for k, v in (kv.split("=", 1) for kv in a.params)}
    sql = (a.sql_file if a.sql_file.exists() else HERE / a.sql_file).read_text()

    try:
        con = psycopg.connect(a.dsn, autocommit=True)
    except psycopg.OperationalError as exc:
        raise SystemExit(f"Can't connect to {a.dsn}\n{exc}")
    if not con.execute("SELECT 1 FROM pg_namespace WHERE nspname = %s", (a.db,)).fetchone():
        raise SystemExit(f"Schema {a.db} not found. Build it first (see ../05_load/README.md).")
    con.execute(pgsql.SQL("SET search_path TO {}").format(pgsql.Identifier(a.db)))
    if a.workers is not None:
        con.execute(f"SET max_parallel_workers_per_gather = {int(a.workers)}")

    if a.explain or a.analyze:
        prefix = "EXPLAIN (ANALYZE, BUFFERS) " if a.analyze else "EXPLAIN "
        for (line,) in con.execute(prefix + sql, params).fetchall():
            print(line)
    else:
        times = []
        for _ in range(a.runs):
            t0 = time.perf_counter()
            cur = con.execute(sql, params)
            rows = cur.fetchall()
            times.append((time.perf_counter() - t0) * 1000)
        cols = [d.name for d in cur.description]
        print(" | ".join(cols))
        for r in rows[:20]:
            print(" | ".join(str(v) for v in r))
        if len(rows) > 20:
            print(f"... ({len(rows) - 20} more)")
        label = f"median of {a.runs}" if a.runs > 1 else "one run"
        print(f"{len(rows)} rows in {statistics.median(times):.2f} ms ({label})")
    con.close()


if __name__ == "__main__":
    main()
