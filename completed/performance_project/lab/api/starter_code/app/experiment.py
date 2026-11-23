"""SQLite harness for the measurement API (see lab/api/03_experiment_py/).

Two jobs:

1. ``get_exp_db``: a FastAPI dependency that reads ``?db=`` (e.g. ``noidx_1m``),
   opens that database file, and hands the route an ``ExpDB``.
2. ``run_query`` / ``run_write``: load a query's SQL from
   ``engines/01_sqlite/06_queries/``, run it, time it, collect its plan, and
   return the result envelope from the route contract:

    {"engine": "sqlite", "dataset": "store", "size": "1m", "variant": "idx",
     "query_id": "Q07", "elapsed_ms": 12.4, "row_count": 10,
     "plan": ["..."], "rows": [...]}

Usage in main.py:

    @app.get("/customers")
    def q01_customer(customer_id: int, db: ExpDB = Depends(get_exp_db)):
        return run_query(db, "Q01", {"customer_id": customer_id})

Porting to another engine means rewriting this file. main.py, the driver, and
the load test don't change.
"""

from __future__ import annotations

import os
import sqlite3
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterator

from fastapi import HTTPException, Query

# FIELD_GUIDE: where the field-guide clone is, if this folder was copied out of it
ROOT = Path(os.environ.get("FIELD_GUIDE", Path(__file__).resolve().parents[4])).expanduser()
DATA_DIR = Path(os.environ.get("DATA_DIR", ROOT / "datasets" / "store" / "generated" / "sqlite"))
SQL_DIR = ROOT / "engines" / "01_sqlite" / "06_queries"

# 08_concurrency sets this to 0 to watch "database is locked" happen.
BUSY_TIMEOUT_MS = int(os.environ.get("BUSY_TIMEOUT_MS", "5000"))

# idx_10k, noidx_1m, ... plus the scratch copy 08_concurrency writes into
DB_NAME_PATTERN = r"^((idx|noidx)_(10k|100k|1m|practice)|writes)$"


@dataclass
class ExpDB:
    """An open connection plus which database it is, for the envelope."""

    con: sqlite3.Connection
    name: str

    @property
    def variant(self) -> str:
        return self.name.split("_")[0]

    @property
    def size(self) -> str | None:
        return self.name.split("_")[1] if "_" in self.name else None


def get_exp_db(
    db: str = Query("idx_100k", pattern=DB_NAME_PATTERN,
                    description="which database to query, e.g. noidx_1m"),
) -> Iterator[ExpDB]:
    path = DATA_DIR / f"{db}.db"
    if not path.exists():
        raise HTTPException(404, f"{path.name} not found in {DATA_DIR}. "
                                 "Run datasets/store/generator/make_dbs.py")
    # journal_mode=WAL is already stored in the file by make_dbs.py
    con = sqlite3.connect(path, check_same_thread=False, timeout=BUSY_TIMEOUT_MS / 1000)
    con.row_factory = sqlite3.Row
    try:
        con.execute("PRAGMA foreign_keys = ON")
        con.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
        con.execute("PRAGMA synchronous = NORMAL")
    except sqlite3.OperationalError as exc:   # can be "database is locked" under load
        con.close()
        raise HTTPException(503, f"database error: {exc}") from exc
    try:
        yield ExpDB(con, db)
    finally:
        con.close()


def load_sql(query_id: str) -> str:
    """'Q07' -> 06_queries/q07.sql, 'Q11-fast' -> 06_queries/q11_fast.sql"""
    path = SQL_DIR / (query_id.lower().replace("-", "_") + ".sql")
    return path.read_text()


def _clean(params: dict[str, Any] | None) -> dict[str, Any]:
    # dates arrive as datetime.date; the schema stores ISO text
    return {k: v.isoformat() if isinstance(v, date) else v for k, v in (params or {}).items()}


def _envelope(db: ExpDB, query_id: str, elapsed_ms: float, plan: list, rows: list) -> dict:
    return {
        "engine": "sqlite",
        "dataset": "store",
        "size": db.size,
        "variant": db.variant,
        "query_id": query_id,
        "elapsed_ms": round(elapsed_ms, 3),
        "row_count": len(rows),
        "plan": plan,
        "rows": [dict(r) for r in rows],
    }


def run_query(db: ExpDB, query_id: str, params: dict[str, Any] | None = None) -> dict:
    """Run one SELECT and return its rows, its plan, and how long it took.

    elapsed_ms times execute + fetchall (the database work) only: not the HTTP
    round trip, JSON encoding, or the EXPLAIN.
    """
    sql, params = load_sql(query_id), _clean(params)
    try:
        plan = [r["detail"] for r in db.con.execute("EXPLAIN QUERY PLAN " + sql, params)]
        t0 = time.perf_counter()
        rows = db.con.execute(sql, params).fetchall()
        elapsed_ms = (time.perf_counter() - t0) * 1000
    except sqlite3.Error as exc:
        raise HTTPException(503, f"database error: {exc}") from exc
    return _envelope(db, query_id, elapsed_ms, plan, rows)


def run_write_many(db: ExpDB, query_id: str, rows_params: list[dict[str, Any]]) -> dict:
    """Run one INSERT ... RETURNING per item, all inside ONE transaction.

    Every row is written, then a single commit makes them durable together.
    elapsed_ms covers the whole batch, commit included.
    """
    sql = load_sql(query_id)
    params = [_clean(p) for p in rows_params]
    try:
        plan = [r["detail"] for r in db.con.execute("EXPLAIN QUERY PLAN " + sql, params[0])] if params else []
        t0 = time.perf_counter()
        with db.con:  # one transaction: commits once on success, rolls back on error
            rows = [r for p in params for r in db.con.execute(sql, p).fetchall()]
        elapsed_ms = (time.perf_counter() - t0) * 1000
    except sqlite3.Error as exc:
        raise HTTPException(503, f"database error: {exc}") from exc
    return _envelope(db, query_id, elapsed_ms, plan, rows)


def run_write(db: ExpDB, query_id: str, params: dict[str, Any] | None = None) -> dict:
    """Run one INSERT/UPDATE ... RETURNING inside a transaction and commit it.

    EXPLAIN QUERY PLAN doesn't execute the statement, so collecting the plan
    doesn't write anything. A lock that outlasts busy_timeout becomes a 503
    with SQLite's exact message, e.g. "database is locked".
    """
    sql, params = load_sql(query_id), _clean(params)
    try:
        plan = [r["detail"] for r in db.con.execute("EXPLAIN QUERY PLAN " + sql, params)]
        t0 = time.perf_counter()
        with db.con:  # commits on success, rolls back on error
            rows = db.con.execute(sql, params).fetchall()
        elapsed_ms = (time.perf_counter() - t0) * 1000
    except sqlite3.Error as exc:
        raise HTTPException(503, f"database error: {exc}") from exc
    return _envelope(db, query_id, elapsed_ms, plan, rows)
