#!/usr/bin/env python3
"""
run_query.py -- run one catalog query by hand, with its $parameters bound.

The DuckDB shell has no `.param set`, so this does it for you. From
engines/02_duckdb/06_queries/:

    python3 run_query.py q01.sql customer_id=7
    python3 run_query.py q03.sql start=2025-03-01 end=2025-03-08 --db ~/5303_data/duckdb/idx_1m.duckdb
    python3 run_query.py q04.sql customer_id=42 --db ~/5303_data/duckdb/idx_1m.duckdb --analyze
    python3 run_query.py q09.sql --db ~/5303_data/duckdb/idx_1m.duckdb --runs 5 --threads 1

--explain prints the plan DuckDB chose before running; --analyze runs the
query and prints the plan with real row counts and times per operator.
--runs N runs it N times and reports the median, so the first (cold) run
doesn't decide the number. --threads limits how many CPU cores DuckDB uses.
The database opens read-only, so the measurement API can keep it open too.

Needs: pip install duckdb
"""

from __future__ import annotations

import argparse
import statistics
import time
from pathlib import Path

import duckdb

HERE = Path(__file__).resolve().parent
DEFAULT_DB = HERE.parent / "05_load" / "store_classroom.duckdb"


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
    p.add_argument("params", nargs="*", help="name=value for each $name in the query")
    p.add_argument("--db", type=Path, default=DEFAULT_DB, help=f"default: {DEFAULT_DB.name} from 05_load/")
    p.add_argument("--runs", type=int, default=1, help="run it N times and report the median time")
    p.add_argument("--threads", type=int, help="CPU threads DuckDB may use (default: all cores)")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--explain", action="store_true", help="show the plan instead of the rows")
    mode.add_argument("--analyze", action="store_true", help="run it and show the plan with actual rows and times")
    a = p.parse_args(argv)

    params = dict(kv.split("=", 1) for kv in a.params)
    params = {k: value(v) for k, v in params.items()}
    sql = (a.sql_file if a.sql_file.exists() else HERE / a.sql_file).read_text()

    db = a.db.expanduser()
    if not db.exists():
        raise SystemExit(f"{db} not found. Build it first (see ../05_load/README.md).")
    con = duckdb.connect(str(db), read_only=True)
    if a.threads:
        con.execute(f"SET threads = {a.threads}")
    if a.explain or a.analyze:
        prefix = "EXPLAIN ANALYZE " if a.analyze else "EXPLAIN "
        for _, plan in con.execute(prefix + sql, params).fetchall():
            print(plan)
    else:
        times = []
        for _ in range(a.runs):
            t0 = time.perf_counter()
            rows = con.execute(sql, params).fetchall()
            times.append((time.perf_counter() - t0) * 1000)
        con.sql(sql, params=params).show()
        label = f"median of {a.runs}" if a.runs > 1 else "one run"
        print(f"{len(rows)} rows in {statistics.median(times):.2f} ms ({label})")
    con.close()


if __name__ == "__main__":
    main()
