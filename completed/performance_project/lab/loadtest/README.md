# loadtest

[loadtest.py](loadtest.py) fires N requests **at the same time** at one route,
then reports what happened. Its job is to trigger contention, not to
benchmark.

```bash
# from lab/api/starter_code/, with the API running and its .venv active
python ../../loadtest/loadtest.py --method POST --path "/purchases?db=writes" --n 200
python ../../loadtest/loadtest.py --path "/stats/revenue_by_state?db=idx_100k" --n 200
```

| Option       | Default                | Does                                     |
| ------------ | ---------------------- | ---------------------------------------- |
| `--n`        | 100                    | how many requests to send at once        |
| `--method`   | `GET`                  | `POST` sends a sample purchase as JSON   |
| `--path`     | `/purchases?db=writes` | the route, including `?db=`              |
| `--base`     | `http://127.0.0.1:8001`| the API                                  |
| `--timeout`  | 30                     | seconds before a request gives up        |

## Output

```
POST http://127.0.0.1:8001/purchases?db=writes  x200  in 0.82s
  201: 33
  503: 167
  succeeded/sec: 40.2
  latency ms (all requests): p50 348.0  p95 718.0  p99 754.2  max 771.1
  latency ms (successes):    p50 270.3  p95 674.9
  --- 503 ---
  {"detail":"database error: database is locked"}
```

- **Status codes:** how many succeeded (`201`) and how many the database
  refused (`503`). `EXC` means the request itself failed, e.g. a timeout.
- **succeeded/sec:** successful requests divided by wall-clock time.
- **Latency percentiles:** p95 is the time 95% of requests finished within.
  The *all requests* line includes failures, which can be fast: a refusal
  doesn't wait.
- **One example body per failure type:** the engine's exact message.

## Before you write

Never load-test the experiment databases. Copy one to the scratch name the
`writes` value points at:

```bash
cp datasets/store/generated/sqlite/idx_100k.db datasets/store/generated/sqlite/writes.db
```

The sample purchase uses customer 1 and card 1, which belong together in
every database `make_dbs.py` builds.

See [load_scenarios.md](../load_scenarios.md) for which scenarios each
engine runs.
