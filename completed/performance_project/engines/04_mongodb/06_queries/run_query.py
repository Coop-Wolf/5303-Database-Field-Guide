#!/usr/bin/env python3
"""
run_query.py -- run one catalog command by hand, with its {{placeholders}} filled in.

From engines/04_mongodb/06_queries/:

    python3 run_query.py q01.json customer_id=7                       # database classroom
    python3 run_query.py q03.json start=2025-03-01 end=2025-03-08 --db idx_1m
    python3 run_query.py q04.json customer_id=20912 --db idx_1m --explain
    python3 run_query.py q09.json --db idx_1m --runs 5
    python3 run_query.py q04.json customer_id=20912 --db idx_1m --show-command

--db names the database (idx_1m, noidx_10k, classroom, ...). --explain prints
the plan the API's `plan` field shows (from explain "executionStats"); add
--raw for MongoDB's whole explain document. --runs N reports the median of N.
--show-command prints the exact command sent, ready to paste into mongosh as
db.runCommand(...).

Uses the same placeholder rules and plan formatting as the measurement API
(lab/api/starter_code/app/experiment_mongo.py), so the two always agree.

Connection: $MONGO_URL, else the course default.
Needs: pip install pymongo fastapi   (fastapi only because the harness imports it)
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

from bson.decimal128 import Decimal128

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "lab" / "api" / "starter_code"))
from app import experiment_mongo as em  # noqa: E402


def value(text: str):
    """'7' -> 7, '9.99' -> 9.99, anything else stays text (dates included)."""
    for cast in (int, float):
        try:
            return cast(text)
        except ValueError:
            pass
    return text


def to_mongosh(obj, indent: int = 0) -> str:
    """The command as mongosh JavaScript: real dates and decimals, not strings."""
    pad, inner = "  " * indent, "  " * (indent + 1)
    if isinstance(obj, dict):
        if not obj:
            return "{}"
        items = [f"{inner}{json.dumps(k)}: {to_mongosh(v, indent + 1)}" for k, v in obj.items()]
        return "{\n" + ",\n".join(items) + "\n" + pad + "}"
    if isinstance(obj, list):
        return "[" + ", ".join(to_mongosh(v, indent + 1) for v in obj) + "]"
    if isinstance(obj, datetime):
        return f'ISODate("{obj.strftime("%Y-%m-%dT%H:%M:%SZ")}")'
    if isinstance(obj, Decimal128):
        return f'NumberDecimal("{obj}")'
    return json.dumps(obj)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("json_file", type=Path)
    p.add_argument("params", nargs="*", help="name=value for each {{name}} in the command")
    p.add_argument("--db", default="classroom", help="database to run in (default: classroom)")
    p.add_argument("--runs", type=int, default=1, help="run it N times and report the median time")
    p.add_argument("--explain", action="store_true", help="show the plan instead of the documents")
    p.add_argument("--raw", action="store_true", help="with --explain: MongoDB's whole explain document")
    p.add_argument("--show-command", action="store_true", help="print the command, filled in, and stop")
    a = p.parse_args(argv)

    params = {k: value(v) for k, v in (kv.split("=", 1) for kv in a.params)}
    path = a.json_file if a.json_file.exists() else HERE / a.json_file
    raw = json.loads(path.read_text())
    raw.pop("//", None)
    if "steps" in raw:
        raise SystemExit("That's a write recipe (Q15). Run it through the API: POST /purchases?db=writes")
    cmd = em.bind(raw, params)

    if a.show_command:
        print("db.runCommand(" + to_mongosh(cmd) + ")")
        return
    client = em.client()
    if a.db not in client.list_database_names():
        raise SystemExit(f"Database {a.db} not found. Build it first (see ../05_load/README.md).")
    db = client[a.db]

    if a.explain:
        e = db.command({"explain": copy.deepcopy(cmd), "verbosity": "executionStats"})
        if a.raw:
            print(json.dumps(e, indent=2, default=str))
        else:
            print("\n".join(em.plan_lines(e)))
        return

    times = []
    for _ in range(a.runs):
        t0 = time.perf_counter()
        docs = list(db.cursor_command(copy.deepcopy(cmd)))
        times.append((time.perf_counter() - t0) * 1000)
    for d in em._rows(docs)[:20]:
        print(d)
    if len(docs) > 20:
        print(f"... ({len(docs) - 20} more)")
    label = f"median of {a.runs}" if a.runs > 1 else "one run"
    print(f"{len(docs)} documents in {statistics.median(times):.2f} ms ({label})")


if __name__ == "__main__":
    main()
