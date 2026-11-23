# Load Scenarios

Standard shapes of traffic, sent with [loadtest.py](loadtest/README.md).
Every engine runs the scenarios that tell you something about it, and says
why it skips the others. "Nothing to see here, because…" is a valid result.

Run every scenario against the scratch database (`db=writes`), never the
experiment databases. Commands below run from `lab/api/starter_code/`.

## The scenarios

### S1: read-heavy

Many readers at once, no writers. Does the engine let reads run in parallel?

```bash
python ../../loadtest/loadtest.py --n 500 --path "/stats/revenue_by_state?db=writes"
```

### S2: write-heavy

Many writers at once, all inserting. How does the engine serialize writes,
and what happens to the writers that have to wait?

```bash
python ../../loadtest/loadtest.py --n 200 --method POST --path "/purchases?db=writes"
python ../../loadtest/loadtest.py --n 500 --method POST --path "/purchases?db=writes"
```

### S3: hot row (PostgreSQL script; API route pending)

Many writers **updating the same row**, e.g. decrementing one product's
inventory. This separates engines that lock a row from engines that lock
more.

> **PostgreSQL** and **MongoDB** run it without the API: each unit's
> `hot_row.py` ([PostgreSQL](../engines/03_postgres/08_concurrency/hot_row.py),
> [MongoDB](../engines/04_mongodb/08_concurrency/hot_row.py)) has many
> clients sell one product's stock four different ways, and counts the
> sales that get lost.
>
> **Status (API):** waiting on an `UPDATE` route. The `store` schema has nothing to
> update yet; the `inventory` column in
> [people_products](../datasets/people_products/README.md) will provide one.

### S4: mixed 90/10

Mostly reads with some writes, like most real applications. Do reads keep
flowing while writes happen?

```bash
python ../../loadtest/loadtest.py --n 500 --path "/customers?customer_id=7&db=writes" \
    --write-share 0.1 --write-path "/purchases?db=writes"
```

### S5: burst

S2 with a much larger `--n` (1,000 or more), all at once. What fails first:
the database, the API server, or the client?

```bash
python ../../loadtest/loadtest.py --n 2000 --method POST --path "/purchases?db=writes" --timeout 60
```

## What to record

For every run: the scenario, `--n`, the server settings you started the API
with, and from the output: successes, failures, seconds, succeeded/sec, p95,
and **the exact text of one failure**.

## Which engine runs which

Each unit's `08_concurrency/` decides, and says why.

| Engine   | S1 | S2 | S3 | S4 | S5 | Unit                                                        |
| -------- | :-: | :-: | :-: | :-: | :-: | ---------------------------------------------------------- |
| SQLite   | — | ✓ | — | ✓ | optional | [08_concurrency](../engines/01_sqlite/08_concurrency/README.md) |
| DuckDB   | ✓ | ✓ | — | ✓ | optional | [08_concurrency](../engines/02_duckdb/08_concurrency/README.md) |
| Postgres | ✓ | ✓ | ✓ (script) | ✓ | optional | [08_concurrency](../engines/03_postgres/08_concurrency/README.md) |
| MongoDB  | ✓ | ✓ | ✓ (script) | ✓ | optional | [08_concurrency](../engines/04_mongodb/08_concurrency/README.md) |
| Redis    |   |   |   |   |   | not written yet                                             |
