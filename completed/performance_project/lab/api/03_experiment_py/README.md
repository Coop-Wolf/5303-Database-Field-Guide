# 03 — experiment.py: The Per-Engine Harness

[starter_code/app/experiment.py](../starter_code/app/experiment.py) is the
only file that knows which database engine is behind the API. Routes,
the driver, and the load test don't.

## Its two jobs

### 1. Hand a route a connection: `get_exp_db`

```python
def q01_customer(customer_id: int, db: ExpDB = Depends(get_exp_db)):
```

For every request, `get_exp_db`:

1. reads `?db=` and checks it against the allowed names (a bad name is a 422);
2. finds the file in `DATA_DIR`, or answers 404 if it hasn't been built;
3. opens a connection and sets the per-connection options:
   `foreign_keys = ON`, `busy_timeout`, `synchronous = NORMAL`;
4. yields an `ExpDB` (the connection plus the database's name), and closes
   the connection after the response goes out.

### 2. Run, time, and explain a query: `run_query` and `run_write`

```python
return run_query(db, "Q07", {"start": start, "end": end})
```

1. Load the SQL from `engines/01_sqlite/06_queries/q07.sql`. `"Q11-fast"`
   becomes `q11_fast.sql`.
2. Collect the plan with `EXPLAIN QUERY PLAN`, which doesn't execute anything.
3. Start the timer, `execute()` **and** `fetchall()`, stop the timer.
4. Build the [envelope](../02_route_contract/README.md#result-envelope).

`run_write` does the same for Q15, inside a transaction it commits. Any
`sqlite3.Error` becomes a 503 carrying SQLite's own message.

Dates arrive as `datetime.date` objects. The harness converts them to ISO
text (`2025-03-01`), because that's how the schema stores dates.

## Connection strategy differs by engine

| Engine            | Strategy                       | Why                                                                                  |
| ----------------- | ------------------------------ | ------------------------------------------------------------------------------------ |
| SQLite            | open per request               | It's a file. Opening one costs microseconds.                                         |
| DuckDB            | **one per file, per process**, a cursor per request | Opening a file costs milliseconds, and only one process may hold it for writing. |
| Postgres, MongoDB, Redis | **one pool, opened at startup** | Connecting over a network costs milliseconds. Per request, you'd be timing connection setup instead of the query. |

## Porting to a new engine

| Changes                                                     | Stays the same                          |
| ----------------------------------------------------------- | --------------------------------------- |
| how `get_exp_db` connects, and what `?db=` points at       | every route in `main.py`                |
| how the plan is collected (that unit's `07_explain/`)       | the envelope's fields                   |
| which errors become 503s                                    | `driver.py`, `loadtest.py`              |
| where `load_sql` finds the query files, and their extension | the query IDs                           |

That's the payoff of the contract: one new file per engine, and the whole
experiment runs against it.

DuckDB's is [experiment_duckdb.py](../starter_code/app/experiment_duckdb.py),
PostgreSQL's [experiment_postgres.py](../starter_code/app/experiment_postgres.py),
and MongoDB's [experiment_mongo.py](../starter_code/app/experiment_mongo.py).
Setting `ENGINE=duckdb`, `postgres`, or `mongodb` makes `main.py` import one
of them instead of `experiment.py`; see each engine's §7
([DuckDB](../../../engines/02_duckdb/07_explain/README.md),
[PostgreSQL](../../../engines/03_postgres/07_explain/README.md),
[MongoDB](../../../engines/04_mongodb/07_explain/README.md)).
MongoDB's query files are JSON commands, not SQL, but `load_sql` and the
routes don't know the difference.

> **A pool has a trap.** The PostgreSQL harness borrows a connection inside
> `run_query`, not in `get_exp_db`, and returns it before `run_query`
> returns. FastAPI runs sync routes and dependencies on a pool of 40
> threads; if the *dependency* borrowed from a 10-connection pool, 40
> threads could end up waiting for a connection while the 10 requests that
> hold one wait for a free thread to finish. Under load, every request
> hangs. Holding a scarce resource across a wait for another scarce
> resource is how deadlocks start, in an API as in a database.
