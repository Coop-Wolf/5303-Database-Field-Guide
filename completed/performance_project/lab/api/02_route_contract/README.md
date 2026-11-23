# 02 — The Route Contract

The one thing every engine unit must follow: **the same paths, returning the
same envelope.** That's what lets one `driver.py` and one `loadtest.py` work
against any engine.

## Routes

**Route convention (course rule, applies to every engine):**

| Rule | Example |
| ---- | ------- |
| The path names *what* is asked for; every value goes in the query string | `/customers?customer_id=7`, not `/customers/7` |
| Path segments: lowercase plural nouns, `_` between words | `/stats/revenue_by_state` |
| Parameter names match the column/field they filter | `customer_id`, `department`, `state` |
| Every route accepts `db=` (size + variant) | `?customer_id=7&db=idx_1m` |
| A rewritten "fast" version is the same path + `/fast` | `/purchases/page/fast?after_id=900000` |
| Writes use `POST` with a JSON body; no values in the path | `POST /purchases?db=writes` |

- Every route, method, and parameter list lives in **one table**: the
  [query catalog](../../../datasets/store/query_catalog.md). Units don't invent routes.
- Note for Fall 2026 A01: Q01, Q04, and Q06 used path IDs (`/customers/{customer_id}`)
  and two paths used hyphens. The field guide follows the rule above.

### `db=` values

| Value             | Database                                                      |
| ----------------- | ------------------------------------------------------------- |
| `idx_<size>`      | `10k`, `100k`, or `1m`, with every index                      |
| `noidx_<size>`    | the same rows, with only `PRIMARY KEY` / `UNIQUE` indexes     |
| `idx_practice`    | a throwaway 100k copy you can break                           |
| `writes`          | the scratch copy that 08_concurrency writes into              |

Anything else gets a 422. A valid name whose database hasn't been built gets
a 404.

## Result envelope

```json
{
  "engine": "sqlite", "dataset": "store", "size": "1m", "variant": "idx",
  "query_id": "Q07", "elapsed_ms": 12.4, "row_count": 10,
  "plan": ["..."], "rows": [ ... ]
}
```

| Field        | Meaning                                                                                    |
| ------------ | ------------------------------------------------------------------------------------------ |
| `engine`     | `sqlite`, `duckdb`, `postgres`, `mongodb`, or `redis`                                      |
| `dataset`    | `store` for now                                                                            |
| `size`       | `10k`, `100k`, `1m`, `practice`, or `null` for `writes`                                    |
| `variant`    | `idx`, `noidx`, or `writes`                                                                |
| `query_id`   | the catalog ID: `Q07`, or `Q11-fast` for a rewrite                                         |
| `elapsed_ms` | time the database spent, in milliseconds (see below)                                       |
| `row_count`  | `len(rows)`                                                                                |
| `plan`       | the engine's plan, one line per list item, in whatever form that engine reports it         |
| `rows`       | the result, one JSON object per row                                                        |

### What `elapsed_ms` measures

From sending the query until **every row is in Python**. Some drivers return
from `execute()` as soon as the first row is ready, so a lazy cursor must be
drained (`fetchall()`) inside the timer, or a slow query looks fast.

It does **not** include the HTTP round trip, JSON encoding, or collecting the
plan. The driver compares database work, not web-server overhead.

### Collecting the plan must not repeat or change work

- For a **read**, ask for the plan *after* the timed run, outside the timer.
  SQLite's `EXPLAIN QUERY PLAN` doesn't execute anything. DuckDB, PostgreSQL,
  and MongoDB use their executing forms (`EXPLAIN ANALYZE`, MongoDB
  `executionStats`): those run the read a second time, untimed, because only
  they show real row counts, and in DuckDB whether an index was used at all.
- Never use an executing form on a **write**, unless it runs inside a
  transaction that's rolled back. Otherwise every request writes twice. Use
  plain `EXPLAIN` (or, in MongoDB, list the write's steps).

### Errors

| Situation                                   | Response                                          |
| ------------------------------------------- | ------------------------------------------------- |
| Bad or missing parameter, unknown `db=`     | **422**, from FastAPI's validation                |
| `db=` names a database that isn't built     | **404**                                           |
| The engine refuses (locked, timeout, ...)   | **503** with the engine's **exact** message in `detail` |

The exact message matters. In 08_concurrency, `database is locked` is the
evidence.

## In the starter code

[experiment.py](../starter_code/app/experiment.py) builds the envelope, so a
route never does. See [03 experiment.py](../03_experiment_py/README.md).
