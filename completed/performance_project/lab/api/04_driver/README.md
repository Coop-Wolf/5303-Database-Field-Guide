# 04 — driver.py: Running the Experiment

[starter_code/driver.py](../starter_code/driver.py) knows the route contract
and nothing about databases. It calls every read route against every
database, several times each, and keeps the median.

```bash
python -m app.main                     # terminal 1: the API
python driver.py --sizes 10k           # terminal 2: quick check
python driver.py                       # the full run, ~20 s for SQLite
```

| Option                 | Does                                                          |
| ---------------------- | ------------------------------------------------------------- |
| `--sizes 10k 100k`     | only these sizes (skip 1m while debugging)                    |
| `--only Q08 Q11-fast`  | only these query IDs                                          |
| `--runs 5`             | calls per (query, database); the median is kept               |
| `--base URL`           | another API, e.g. another engine's on another port            |
| `--out DIR`            | write `results.csv` and `results.md` here instead of `results/` |

## What it does

For each database (`noidx_10k`, `idx_10k`, ... `idx_1m`), and each query in
the catalog:

1. Fill in the parameters. Two of them depend on the database:
   - `{whale}`: the customer with the most purchases, so Q01, Q04, and Q06
     do real work;
   - `{deep}`: a `purchase_id` 90% of the way through, so Q11's `OFFSET`
     really is deep.
2. Call the route `--runs` times and read `elapsed_ms` from each response.
3. Keep the **median**, which ignores the occasional slow outlier.

Q15 isn't in the driver. Writes are measured with
[loadtest](../../loadtest/README.md).

## What it writes

| File                  | Contents                                                                 |
| --------------------- | ------------------------------------------------------------------------ |
| `results/results.md`  | one row per query, one column per database, ready to paste into FINDINGS |
| `results/results.csv` | one row per (query, database), with the row count and the full plan      |

## Warm cache

After the first call, the data a query needs is already in memory. The
median of 5 therefore measures **warm** performance: how the query behaves
in a running application, not right after a reboot. Say so in your FINDINGS.

## Common failures

| Message                                   | Cause                                                                         |
| ----------------------------------------- | ----------------------------------------------------------------------------- |
| `API not reachable at http://...`         | Start the API first: `python -m app.main`                                     |
| `idx_1m.db not found`                     | Build the databases: `python3 datasets/store/generator/make_dbs.py`           |
| `Q03 /purchases on noidx_10k: HTTP 404`   | That route doesn't exist yet. Write it, or skip it with `--only`.             |
| `HTTP 422`                                | The route's parameter names or types don't match the catalog                  |

## Driver vs. load test

The driver sends **one request at a time** and measures how long each query
takes. [loadtest](../../loadtest/README.md) sends **many at once** and
measures what breaks. Different questions, different tools.
