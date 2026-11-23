"""PostgreSQL harness for the measurement API (see lab/api/03_experiment_py/).

The same two jobs as experiment.py, for PostgreSQL. Start the API with it by
setting ENGINE:

    ENGINE=postgres PORT=8003 RELOAD=0 python -m app.main

1. ``get_exp_db``: reads ``?db=`` (e.g. ``noidx_1m``), borrows a connection
   from the pool, and points it at that **schema** with ``search_path``.
   The experiment "databases" are schemas inside one database here; see
   engines/03_postgres/05_load/build_postgres.py.
2. ``run_query`` / ``run_write``: load a query's SQL from
   ``engines/03_postgres/06_queries/``, run it, time it, collect its plan, and
   return the result envelope with ``"engine": "postgres"``.

What's different from the file engines:

* **A connection pool, opened once per process.** Connecting to a server
  costs milliseconds (a network round trip, a login, a new server process).
  Per request, you'd be timing the handshake instead of the query
  (fairness rule 7). POOL_MAX sets how many connections each worker process
  may hold.
* **Every connection can write.** There's no file lock: concurrent writers
  are the server's job. 08_concurrency measures how it does it.
* **The plan comes from EXPLAIN (ANALYZE, BUFFERS)**, run after the timed
  query (untimed): real row counts, times, and pages per plan node.

Settings (environment variables):

    DATABASE_URL        default postgresql://student:student@localhost:5432/course
    POOL_MAX            connections per worker process (default 10)
    SYNCHRONOUS_COMMIT  on (default) or off: does COMMIT wait for the WAL
                        to reach disk? 08_concurrency compares the two.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterator

import psycopg
from fastapi import HTTPException, Query
from psycopg_pool import ConnectionPool, PoolTimeout

# FIELD_GUIDE: where the field-guide clone is, if this folder was copied out of it
ROOT = Path(os.environ.get("FIELD_GUIDE", Path(__file__).resolve().parents[4])).expanduser()
SQL_DIR = ROOT / "engines" / "03_postgres" / "06_queries"

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://student:student@localhost:5432/course")
POOL_MAX = int(os.environ.get("POOL_MAX", "10"))
SYNCHRONOUS_COMMIT = os.environ.get("SYNCHRONOUS_COMMIT", "on")

# Schema names, not file names: idx_10k, noidx_1m, ... plus the scratch copy
DB_NAME_PATTERN = r"^((idx|noidx)_(10k|100k|1m|practice)|writes)$"

_pool: ConnectionPool | None = None
_pool_lock = threading.Lock()
_schemas: set[str] = set()


@dataclass
class ExpDB:
    """Which schema this request uses, plus a pooled connection borrowed on demand.

    The connection is borrowed the first time a route touches ``db.con`` and
    returned by run_query / run_write before they return. Borrowing it in
    get_exp_db instead looks simpler but deadlocks under load: FastAPI runs
    sync routes and dependencies on a pool of 40 threads, so with a 10-connection
    pool, 40 threads can end up waiting for a connection while the 10 requests
    holding one wait for a free thread to finish and give it back.
    """

    name: str
    _con: psycopg.Connection | None = None

    @property
    def con(self) -> psycopg.Connection:
        if self._con is None:
            try:
                con = pool().getconn()
            except PoolTimeout as exc:
                raise HTTPException(503, f"database error: no free connection ({exc})") from exc
            try:
                if self.name not in _schemas:
                    if not con.execute("SELECT 1 FROM pg_namespace WHERE nspname = %s",
                                       (self.name,)).fetchone():
                        raise HTTPException(404, f"schema {self.name} not found. Run "
                                                 "engines/03_postgres/05_load/build_postgres.py")
                    _schemas.add(self.name)
                con.execute("SELECT set_config('search_path', %s, false)", (self.name,))
            except BaseException:
                pool().putconn(con)
                raise
            self._con = con
        return self._con

    def release(self) -> None:
        if self._con is not None:
            pool().putconn(self._con)
            self._con = None

    @property
    def variant(self) -> str:
        return self.name.split("_")[0]

    @property
    def size(self) -> str | None:
        return self.name.split("_")[1] if "_" in self.name else None


def _configure(con: psycopg.Connection) -> None:
    """Runs once for each new pooled connection."""
    if SYNCHRONOUS_COMMIT not in ("on", "off", "local", "remote_write", "remote_apply"):
        raise ValueError(f"SYNCHRONOUS_COMMIT={SYNCHRONOUS_COMMIT!r}")
    con.execute(f"SET synchronous_commit = {SYNCHRONOUS_COMMIT}")


def pool() -> ConnectionPool:
    """The process-wide pool, opened on first use."""
    global _pool
    with _pool_lock:
        if _pool is None:
            try:
                # prepare_threshold=None: never switch to server-side prepared
                # statements. After 5 runs psycopg would, and PostgreSQL may then
                # use a generic plan, so the timed query and its EXPLAIN could
                # be planned differently.
                _pool = ConnectionPool(DATABASE_URL, min_size=1, max_size=POOL_MAX,
                                       kwargs={"autocommit": True, "prepare_threshold": None},
                                       configure=_configure, open=True, timeout=30)
                _pool.wait(timeout=10)
            except Exception as exc:
                _pool = None
                raise HTTPException(503, f"can't reach PostgreSQL at {DATABASE_URL}: {exc}") from exc
        return _pool


def get_exp_db(
    db: str = Query("idx_100k", pattern=DB_NAME_PATTERN,
                    description="which schema to query, e.g. noidx_1m"),
) -> Iterator[ExpDB]:
    exp = ExpDB(db)
    try:
        yield exp
    finally:
        exp.release()          # a safety net; run_query and run_write release it themselves


def load_sql(query_id: str) -> str:
    """'Q07' -> 06_queries/q07.sql, 'Q11-fast' -> 06_queries/q11_fast.sql"""
    path = SQL_DIR / (query_id.lower().replace("-", "_") + ".sql")
    return path.read_text()


def _clean(params: dict[str, Any] | None) -> dict[str, Any]:
    # ISO text, the same as SQLite gets. psycopg sends a str untyped, so the
    # server reads it as a date where it meets a date column.
    return {k: v.isoformat() if hasattr(v, "isoformat") else v for k, v in (params or {}).items()}


def _rows(cur: psycopg.Cursor, rows: list[tuple]) -> list[dict]:
    cols = [d.name for d in cur.description]
    return [{c: float(v) if isinstance(v, Decimal) else v for c, v in zip(cols, r)} for r in rows]


def _plan(con: psycopg.Connection, sql: str, params: dict, analyze: bool = True) -> list[str]:
    options = "ANALYZE, BUFFERS" if analyze else "COSTS OFF"
    return [line for (line,) in con.execute(f"EXPLAIN ({options}) {sql}", params).fetchall()]


def _envelope(db: ExpDB, query_id: str, elapsed_ms: float, plan: list, rows: list) -> dict:
    return {
        "engine": "postgres",
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

    elapsed_ms times execute + fetchall (the round trip to the server and the
    database work) only: not HTTP, JSON encoding, or the EXPLAIN.
    """
    sql, params = load_sql(query_id), _clean(params)
    try:
        t0 = time.perf_counter()
        cur = db.con.execute(sql, params)
        rows = cur.fetchall()
        elapsed_ms = (time.perf_counter() - t0) * 1000
        rows = _rows(cur, rows)
        plan = _plan(db.con, sql, params)
    except psycopg.Error as exc:
        raise HTTPException(503, f"database error: {exc}") from exc
    finally:
        db.release()
    return _envelope(db, query_id, elapsed_ms, plan, rows)


def run_write(db: ExpDB, query_id: str, params: dict[str, Any] | None = None) -> dict:
    """Run one INSERT/UPDATE ... RETURNING inside a transaction and commit it.

    The plan comes from plain EXPLAIN: EXPLAIN ANALYZE would run the INSERT.
    """
    sql, params = load_sql(query_id), _clean(params)
    try:
        plan = _plan(db.con, sql, params, analyze=False)
        t0 = time.perf_counter()
        with db.con.transaction():                 # commits on success, rolls back on error
            cur = db.con.execute(sql, params)
            rows = cur.fetchall()
        elapsed_ms = (time.perf_counter() - t0) * 1000
        rows = _rows(cur, rows)
    except psycopg.Error as exc:
        raise HTTPException(503, f"database error: {exc}") from exc
    finally:
        db.release()
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
        rows = []
        with db.con.transaction():
            for p in params:
                cur = db.con.execute(sql, p)
                rows += _rows(cur, cur.fetchall())
        elapsed_ms = (time.perf_counter() - t0) * 1000
    except psycopg.Error as exc:
        raise HTTPException(503, f"database error: {exc}") from exc
    finally:
        db.release()
    return _envelope(db, query_id, elapsed_ms, plan, rows)
