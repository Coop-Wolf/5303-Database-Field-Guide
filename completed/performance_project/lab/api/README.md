# Lab: The Measurement API

Why we measure databases *through* an API, and how the pieces fit. Taught once,
during the first engine unit ([SQLite](../../engines/01_sqlite/)), then reused by
every other unit without being taught again.

```
driver.py / loadtest.py  ──HTTP──▶  FastAPI app  ──▶  database
                                     ├─ main.py        routes, one per catalog row
                                     ├─ experiment.py  connection + run_query (per engine)
                                     └─ 06_queries/    the SQL, loaded from the unit
```

| #   | Page                                       | Covers                                                              |
| --- | ------------------------------------------ | ------------------------------------------------------------------- |
| —   | [starter_code/](starter_code/README.md)    | The runnable app: setup, layout, and your three routes              |
| 01  | [FastAPI basics](01_fastapi_basics/)       | Decorators, query params vs. JSON body, validation, `/docs`        |
| 02  | [Route contract](02_route_contract/)       | The shared paths + result envelope every engine implements          |
| 03  | [experiment.py](03_experiment_py/)         | The per-engine harness: connection, `?db=` selection, `run_query()` |
| 04  | [driver.py](04_driver/)                    | How the driver calls routes, takes medians, writes results          |

**When:** after students can query an engine by hand (unit §1–5), before they
run the query catalog through the API (unit §6).
