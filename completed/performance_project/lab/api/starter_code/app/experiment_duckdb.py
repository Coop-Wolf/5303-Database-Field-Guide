"""DuckDB harness for the measurement API (see lab/api/03_experiment_py/).

The same two jobs as experiment.py, for DuckDB. Start the API with it by
setting ENGINE:

    ENGINE=duckdb PORT=8002 RELOAD=0 python -m app.main

1. ``get_exp_db``: reads ``?db=`` (e.g. ``noidx_1m``) and hands the route an
   ``ExpDB`` for that ``.duckdb`` file.
2. ``run_query`` / ``run_write``: load a query's SQL from
   ``engines/02_duckdb/06_queries/``, run it, time it, collect its plan, and
   return the result envelope with ``"engine": "duckdb"``.

Two things differ from SQLite, and both come from how DuckDB opens a file:

* **One connection per file, per process.** Opening a DuckDB file costs
  milliseconds, not microseconds, and only one process may hold it for
  writing. So the first request opens the file and keeps it open; every
  request after that gets its own cursor on that connection.
* **The experiment databases open read-only.** Many processes can read a
  file at once, so you can keep the DuckDB shell open on idx_1m while the API
  runs. ``writes`` opens read-write, and while it's open no other process can
  open it at all. 08_concurrency is about exactly that.

The plan comes from ``EXPLAIN ANALYZE``, which runs the query a second time
(untimed). Plain ``EXPLAIN`` can't say whether a scan will use an index:
DuckDB decides that while the query runs.
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterator

import duckdb
from fastapi import HTTPException, Query

# FIELD_GUIDE: where the field-guide clone is, if this folder was copied out of it
ROOT = Path(os.environ.get("FIELD_GUIDE", Path(__file__).resolve().parents[4])).expanduser()
# Same defaults as engines/02_duckdb/05_load/build_duckdb.py
_SQLITE_DIR = Path(os.environ.get("DATA_DIR", ROOT / "datasets" / "store" / "generated" / "sqlite")).expanduser()
DUCKDB_DIR = Path(os.environ.get("DUCKDB_DIR", _SQLITE_DIR.parent / "duckdb")).expanduser()
SQL_DIR = ROOT / "engines" / "02_duckdb" / "06_queries"

DB_NAME_PATTERN = r"^((idx|noidx)_(10k|100k|1m|practice)|writes)$"

_open: dict[str, duckdb.DuckDBPyConnection] = {}
_open_lock = threading.Lock()


@dataclass
class ExpDB:
    """A cursor for this request plus which database it is, for the envelope."""

    con: duckdb.DuckDBPyConnection
    name: str

    @property
    def variant(self) -> str:
        return self.name.split("_")[0]

    @property
    def size(self) -> str | None:
        return self.name.split("_")[1] if "_" in self.name else None


def _connection(db: str) -> duckdb.DuckDBPyConnection:
    """The process-wide connection to one file, opened on first use."""
    with _open_lock:
        if db not in _open:
            path = DUCKDB_DIR / f"{db}.duckdb"
            if not path.exists():
                raise HTTPException(404, f"{path.name} not found in {DUCKDB_DIR}. "
                                         "Run engines/02_duckdb/05_load/build_duckdb.py")
            try:
                _open[db] = duckdb.connect(str(path), read_only=(db != "writes"))
            except duckdb.Error as exc:   # "Could not set lock on file" if another process has it
                raise HTTPException(503, f"database error: {exc}") from exc
        return _open[db]


def get_exp_db(
    db: str = Query("idx_100k", pattern=DB_NAME_PATTERN,
                    description="which database to query, e.g. noidx_1m"),
) -> Iterator[ExpDB]:
    cur = _connection(db).cursor()
    try:
        yield ExpDB(cur, db)
    finally:
        cur.close()


def load_sql(query_id: str) -> str:
    """'Q07' -> 06_queries/q07.sql, 'Q11-fast' -> 06_queries/q11_fast.sql"""
    path = SQL_DIR / (query_id.lower().replace("-", "_") + ".sql")
    return path.read_text()


def _clean(params: dict[str, Any] | None) -> dict[str, Any]:
    # ISO text, the same as SQLite gets; DuckDB casts it to DATE where it meets a DATE column
    return {k: v.isoformat() if isinstance(v, date) else v for k, v in (params or {}).items()}


def _rows(cur: duckdb.DuckDBPyConnection, rows: list[tuple]) -> list[dict]:
    cols = [d[0] for d in cur.description]
    return [{c: float(v) if isinstance(v, Decimal) else v for c, v in zip(cols, r)} for r in rows]


def _plan(cur: duckdb.DuckDBPyConnection, sql: str, params: dict, analyze: bool = True) -> list[str]:
    """One line per operator, indented by depth:

    HASH_GROUP_BY  out 51 rows  2.10 ms
      TABLE_SCAN purchases [Sequential Scan]  scanned 1,000,000  out 1,000,000  0.84 ms
    """
    mode = "(ANALYZE, FORMAT json)" if analyze else "(FORMAT json)"
    tree = json.loads(cur.execute(f"EXPLAIN {mode} {sql}", params).fetchall()[0][1])
    lines: list[str] = []

    def walk(node: dict, depth: int) -> None:
        name = node.get("operator_name") or node.get("name", "")
        info = node.get("extra_info", {})
        if name in ("EXPLAIN_ANALYZE", "PROJECTION"):   # bookkeeping, not work: show what's under it
            for child in node.get("children", []):
                walk(child, depth)
            return
        parts = [name]
        if "Table" in info:
            parts[0] += " " + info["Table"].split(".")[-1]
        if "Type" in info:
            parts[0] += f" [{info['Type']}]"
        if "Join Type" in info:
            parts[0] += f" [{info['Join Type']}]"
        if info.get("Filters"):
            parts.append(f"filters: {info['Filters']}")
        if node.get("operator_rows_scanned"):
            parts.append(f"scanned {node['operator_rows_scanned']:,}")
        if "operator_cardinality" in node:
            parts.append(f"out {node['operator_cardinality']:,}")
        elif "Estimated Cardinality" in info:
            parts.append(f"~{info['Estimated Cardinality']} rows (estimate)")
        if "operator_timing" in node:
            parts.append(f"{node['operator_timing'] * 1000:.2f} ms")
        lines.append("  " * depth + "  ".join(parts))
        for child in node.get("children", []):
            walk(child, depth + 1)

    for root in (tree["children"] if isinstance(tree, dict) else tree):
        walk(root, 0)
    return lines


def _envelope(db: ExpDB, query_id: str, elapsed_ms: float, plan: list, rows: list) -> dict:
    return {
        "engine": "duckdb",
        "dataset": "store",
        "size": db.size,
        "variant": db.variant,
        "query_id": query_id,
        "elapsed_ms": round(elapsed_ms, 3),
        "row_count": len(rows),
        "plan": plan,
        "rows": rows,
    }


def run_query(db: ExpDB, query_id: str, params: dict[str, Any] | None = None) -> dict:
    """Run one SELECT and return its rows, its plan, and how long it took.

    elapsed_ms times execute + fetchall (the database work) only: not the HTTP
    round trip, JSON encoding, or the EXPLAIN ANALYZE.
    """
    sql, params = load_sql(query_id), _clean(params)
    try:
        t0 = time.perf_counter()
        rows = db.con.execute(sql, params).fetchall()
        elapsed_ms = (time.perf_counter() - t0) * 1000
        rows = _rows(db.con, rows)
        plan = _plan(db.con, sql, params)
    except duckdb.Error as exc:
        raise HTTPException(503, f"database error: {exc}") from exc
    return _envelope(db, query_id, elapsed_ms, plan, rows)


def run_write(db: ExpDB, query_id: str, params: dict[str, Any] | None = None) -> dict:
    """Run one INSERT/UPDATE ... RETURNING inside a transaction and commit it.

    The plan comes from plain EXPLAIN here, because EXPLAIN ANALYZE would
    write the row a second time. A conflict with another transaction becomes
    a 503 with DuckDB's exact message.
    """
    sql, params = load_sql(query_id), _clean(params)
    try:
        plan = _plan(db.con, sql, params, analyze=False)
        t0 = time.perf_counter()
        db.con.execute("BEGIN")
        try:
            rows = db.con.execute(sql, params).fetchall()
            db.con.execute("COMMIT")
        except duckdb.Error:
            db.con.execute("ROLLBACK")
            raise
        elapsed_ms = (time.perf_counter() - t0) * 1000
        rows = _rows(db.con, rows)
    except duckdb.Error as exc:
        raise HTTPException(503, f"database error: {exc}") from exc
    return _envelope(db, query_id, elapsed_ms, plan, rows)


def run_write_many(db: ExpDB, query_id: str, rows_params: list[dict[str, Any]]) -> dict:
    """Run one INSERT ... RETURNING per item, all inside ONE transaction.

    elapsed_ms covers the whole batch, commit included.
    """
    sql = load_sql(query_id)
    params = [_clean(p) for p in rows_params]
    try:
        plan = _plan(db.con, sql, params[0], analyze=False) if params else []
        t0 = time.perf_counter()
        db.con.execute("BEGIN")
        try:
            rows = []
            for p in params:
                rows += _rows(db.con, db.con.execute(sql, p).fetchall())
            db.con.execute("COMMIT")
        except duckdb.Error:
            db.con.execute("ROLLBACK")
            raise
        elapsed_ms = (time.perf_counter() - t0) * 1000
    except duckdb.Error as exc:
        raise HTTPException(503, f"database error: {exc}") from exc
    return _envelope(db, query_id, elapsed_ms, plan, rows)
