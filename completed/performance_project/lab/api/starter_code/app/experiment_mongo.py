"""MongoDB harness for the measurement API (see lab/api/03_experiment_py/).

The same two jobs as experiment.py, for MongoDB. Start the API with it by
setting ENGINE:

    ENGINE=mongodb PORT=8004 RELOAD=0 python -m app.main

1. ``get_exp_db``: reads ``?db=`` (e.g. ``noidx_1m``) and hands the route an
   ``ExpDB`` for that **database** (engines/04_mongodb/05_load/build_mongo.py
   builds one per experiment).
2. ``run_query`` / ``run_write``: load a query's command from
   ``engines/04_mongodb/06_queries/qNN.json``, fill in its ``{{placeholders}}``,
   run it, time it, collect its plan, and return the result envelope with
   ``"engine": "mongodb"``.

What's different from the SQL engines:

* **A query is a database command, not a string of SQL.** Each .json file is
  the command MongoDB receives: ``{"find": ...}`` or ``{"aggregate": ...}``.
  A top-level ``"//"`` key holds the comments (JSON has none); it's removed
  before the command is sent.
* **Placeholders carry types.** ``"{{customer_id}}"`` becomes the value as
  given; ``"{{start:date}}"`` a datetime; ``"{{start:month}}"`` 'YYYY-MM' text;
  ``"{{amount:decimal}}"`` an exact Decimal128.
* **One client per process.** MongoClient keeps its own connection pool and
  borrows a connection only for the length of each operation.
* **A write is several commands** (see q15.json): take the next id from a
  counter document, copy the customer's state, card type, and product name
  in, then insert.
* **The plan** comes from explain with "executionStats", run after the timed
  query (untimed): the winning plan's stages, then how many index keys and
  documents it examined to return what it returned.

Settings (environment variables):

    MONGO_URL      default mongodb://localhost:27017/?directConnection=true
    POOL_MAX       connections per worker process (default 10)
    WRITE_CONCERN  majority (default, MongoDB's own default: the write is on
                   disk before it's acknowledged) or 1 (acknowledged as soon as
                   it's in memory). 08_concurrency compares the two.
    TXN_RETRY      0 (default) or 1: retry a batch transaction that hits a write
                   conflict (the driver's with_transaction), instead of answering 503.
"""

from __future__ import annotations

import copy
import json
import os
import re
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterator

from bson.decimal128 import Decimal128
from fastapi import HTTPException, Query
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from pymongo.write_concern import WriteConcern

# FIELD_GUIDE: where the field-guide clone is, if this folder was copied out of it
ROOT = Path(os.environ.get("FIELD_GUIDE", Path(__file__).resolve().parents[4])).expanduser()
SQL_DIR = ROOT / "engines" / "04_mongodb" / "06_queries"   # same name as the other harnesses

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017/?directConnection=true")
POOL_MAX = int(os.environ.get("POOL_MAX", "10"))
WRITE_CONCERN = os.environ.get("WRITE_CONCERN", "majority")
# Stamped on every write command: db.command() doesn't apply the client's
# write concern for you, so without this the server default would win.
WC = {"w": "majority"} if WRITE_CONCERN == "majority" else {"w": int(WRITE_CONCERN), "j": False}
TXN_RETRY = os.environ.get("TXN_RETRY", "0") == "1"

DB_NAME_PATTERN = r"^((idx|noidx)_(10k|100k|1m|practice)|writes)$"
PLACEHOLDER = re.compile(r"^\{\{(\w+)(?::(\w+))?\}\}$")

_client: MongoClient | None = None
_client_lock = threading.Lock()
_databases: set[str] = set()


def client() -> MongoClient:
    global _client
    with _client_lock:
        if _client is None:
            _client = MongoClient(MONGO_URL, maxPoolSize=POOL_MAX,
                                  serverSelectionTimeoutMS=5000, tz_aware=False)
        return _client


class _MaxIdShim:
    """The starter's Q12-fast route asks every engine one SQL question directly:
    SELECT MAX(purchase_id) FROM purchases. This answers it the MongoDB way."""

    def __init__(self, db):
        self._db = db

    def execute(self, sql: str, *args):
        if " ".join(sql.split()).upper() != "SELECT MAX(PURCHASE_ID) FROM PURCHASES":
            raise NotImplementedError("the MongoDB harness only answers SELECT MAX(purchase_id)")
        top = self._db.purchases.find_one(sort=[("_id", -1)], projection={"_id": 1})
        return _Row((top["_id"] if top else None,))


class _Row:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


@dataclass
class ExpDB:
    """The database this request uses."""

    db: Any
    name: str

    @property
    def con(self) -> _MaxIdShim:
        return _MaxIdShim(self.db)

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
    try:
        if db not in _databases:
            if db not in client().list_database_names():
                raise HTTPException(404, f"database {db} not found. Run "
                                         "engines/04_mongodb/05_load/build_mongo.py")
            _databases.add(db)
    except PyMongoError as exc:
        raise HTTPException(503, f"database error: {exc}") from exc
    yield ExpDB(client()[db], db)


def load_sql(query_id: str) -> dict:
    """'Q07' -> 06_queries/q07.json, 'Q11-fast' -> 06_queries/q11_fast.json, comments removed."""
    path = SQL_DIR / (query_id.lower().replace("-", "_") + ".json")
    doc = json.loads(path.read_text())
    doc.pop("//", None)
    return doc


def _typed(value: Any, kind: str | None) -> Any:
    if kind == "date":
        return value if isinstance(value, datetime) else datetime.fromisoformat(str(value)[:10])
    if kind == "month":
        return str(value)[:7]
    if kind == "decimal":
        return Decimal128(Decimal(str(value)).quantize(Decimal("0.01")))
    return value


def bind(obj: Any, params: dict[str, Any]) -> Any:
    """Replace every "{{name}}" / "{{name:kind}}" string with its typed value."""
    if isinstance(obj, dict):
        return {k: bind(v, params) for k, v in obj.items()}
    if isinstance(obj, list):
        return [bind(v, params) for v in obj]
    if isinstance(obj, str):
        m = PLACEHOLDER.match(obj)
        if m:
            name, kind = m.groups()
            if name not in params:
                raise HTTPException(500, f"no value for placeholder {obj}")
            return _typed(params[name], kind)
    return obj


def _clean(params: dict[str, Any] | None) -> dict[str, Any]:
    return {k: v.isoformat() if isinstance(v, date) else v for k, v in (params or {}).items()}


def _plain(v: Any) -> Any:
    """BSON values -> JSON-friendly ones, the same shapes the SQL engines return."""
    if isinstance(v, Decimal128):
        return float(v.to_decimal())
    if isinstance(v, datetime):
        return v.date().isoformat()
    return v


def _rows(docs: list[dict]) -> list[dict]:
    return [{k: _plain(v) for k, v in d.items()} for d in docs]


def _stage_lines(node: dict, depth: int, out: list[str]) -> None:
    """Classic plan stages: COLLSCAN, IXSCAN, FETCH, SORT, GROUP, ..."""
    if not node:
        return
    name = node.get("stage", "?")
    bits = [name]
    if "indexName" in node:
        bounds = node.get("indexBounds")
        bits.append(f"{node['indexName']} {json.dumps(bounds, default=str) if bounds else ''}".strip())
        if node.get("direction") == "backward":
            bits.append("backward")
    if node.get("filter"):
        bits.append(f"filter {json.dumps(node['filter'], default=str)}")
    if "sortPattern" in node:
        bits.append(f"by {json.dumps(node['sortPattern'])}")
    if "limitAmount" in node:
        bits.append(f"limit {node['limitAmount']}")
    out.append("  " * depth + "  ".join(bits))
    for child in [node.get("inputStage")] + node.get("inputStages", []):
        if child:
            _stage_lines(child, depth + 1, out)


def plan_lines(explain: dict) -> list[str]:
    """Flatten an explain document into one line per step."""
    lines: list[str] = []
    cursor = explain
    stages = explain.get("stages")
    if stages and "$cursor" in stages[0]:
        cursor = stages[0]["$cursor"]
    planner = cursor.get("queryPlanner", {})
    winning = planner.get("winningPlan", {})
    _stage_lines(winning.get("queryPlan", winning), 0, lines)
    st = cursor.get("executionStats", {})
    if st:
        lines.append(f"examined: {st.get('totalKeysExamined', 0):,} index keys, "
                     f"{st.get('totalDocsExamined', 0):,} documents -> returned {st.get('nReturned', 0):,} "
                     f"({st.get('executionTimeMillis', 0)} ms)")
    for s in (stages or [])[1:]:
        name = next((k for k in s if k.startswith("$")), "?")
        extra = []
        if "nReturned" in s:
            extra.append(f"returned {s['nReturned']:,}")
        if "executionTimeMillisEstimate" in s:
            extra.append(f"~{s['executionTimeMillisEstimate']} ms")
        lines.append(f"then {name}  " + "  ".join(extra))
    return lines


def _envelope(db: ExpDB, query_id: str, elapsed_ms: float, plan: list, rows: list) -> dict:
    return {
        "engine": "mongodb",
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
    """Run one find or aggregate command; return its documents, plan, and time.

    elapsed_ms covers sending the command until every document is in Python
    (cursor_command fetches every batch), not HTTP, JSON, or the explain.
    """
    cmd = bind(load_sql(query_id), _clean(params))
    try:
        t0 = time.perf_counter()
        docs = list(db.db.cursor_command(cmd))
        elapsed_ms = (time.perf_counter() - t0) * 1000
        plan = plan_lines(db.db.command({"explain": copy.deepcopy(cmd), "verbosity": "executionStats"}))
    except PyMongoError as exc:
        raise HTTPException(503, f"database error: {exc}") from exc
    return _envelope(db, query_id, elapsed_ms, plan, _rows(docs))


def _take(result: Any, path: str) -> Any:
    for part in path.split("."):
        result = result[int(part)] if isinstance(result, list) else result[part]
    return result


def _write_one(db: ExpDB, recipe: dict, params: dict, session=None) -> dict:
    """Run a write recipe's steps in order; later steps see earlier steps' values."""
    values = dict(params)
    for step in recipe["steps"]:
        cmd = bind(step["command"], values)
        if "aggregate" in cmd:
            result = list(db.db.cursor_command(cmd, session=session))
            if not result:
                raise HTTPException(503, f"database error: step {step['name']} found nothing "
                                         "(does that customer have that card? does the product exist?)")
        else:
            if session is None:                       # inside a transaction, the commit decides
                cmd = {**cmd, "writeConcern": WC}
            result = db.db.command(cmd, session=session)
        for name, path in step.get("take", {}).items():
            values[name] = _take(result, path)
    return {k: _plain(_typed(values[k], "decimal") if k == "amount" else values[k])
            for k in recipe["returning"]}


def run_write(db: ExpDB, query_id: str, params: dict[str, Any] | None = None) -> dict:
    """One purchase: counter -> copy fields in -> insert. No multi-document
    transaction: each step is atomic on its own, and a failure leaves at most
    an unused id."""
    recipe = load_sql(query_id)
    try:
        t0 = time.perf_counter()
        row = _write_one(db, recipe, _clean(params))
        elapsed_ms = (time.perf_counter() - t0) * 1000
    except PyMongoError as exc:
        raise HTTPException(503, f"database error: {exc}") from exc
    plan = [f"step {s['name']}: {next(iter(s['command']))}" for s in recipe["steps"]]
    return _envelope(db, query_id, elapsed_ms, plan, [row])


def run_write_many(db: ExpDB, query_id: str, rows_params: list[dict[str, Any]]) -> dict:
    """Every purchase in ONE multi-document transaction (needs a replica set).
    elapsed_ms covers the whole batch, commit included (and every retry, with
    TXN_RETRY=1). Without TXN_RETRY, a write conflict is a 503 with MongoDB's
    exact message: every batch increments the same counter document."""
    recipe = load_sql(query_id)
    params = [_clean(p) for p in rows_params]
    try:
        t0 = time.perf_counter()
        with client().start_session() as s:
            if TXN_RETRY:
                rows = s.with_transaction(
                    lambda sess: [_write_one(db, recipe, p, session=sess) for p in params],
                    write_concern=WriteConcern(**WC))
            else:
                with s.start_transaction(write_concern=WriteConcern(**WC)):
                    rows = [_write_one(db, recipe, p, session=s) for p in params]
        elapsed_ms = (time.perf_counter() - t0) * 1000
    except PyMongoError as exc:
        raise HTTPException(503, f"database error: {exc}") from exc
    plan = ["one transaction"] + [f"step {s['name']}: {next(iter(s['command']))}" for s in recipe["steps"]]
    return _envelope(db, query_id, elapsed_ms, plan, rows)
