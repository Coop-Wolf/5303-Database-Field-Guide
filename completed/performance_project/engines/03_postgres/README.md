# 03 — PostgreSQL

Relational · client/server · row store (+ extensions)

PostgreSQL is the first **server** in the field guide. SQLite and DuckDB were
libraries inside your program; PostgreSQL is a separate program that owns the
data, and every client, yours included, **connects** to it over the network
as a user. That one change brings everything the file engines couldn't do:
many writers at once, logins and permissions, clients on other machines. It
also brings the costs: a server to run, and a round trip on every query.

Same data, same queries, a different kind of engine.

**You'll come out of this unit able to:**

- run PostgreSQL in Docker and connect to it from `psql`, QueryMux, and Python;
- load the `store` data into schemas, and back it up and restore it;
- design roles and permissions, and prove they work;
- read `EXPLAIN (ANALYZE, BUFFERS)` and say why a query is fast or slow;
- measure what many concurrent writers do, including when they lose updates;
- decide when PostgreSQL is the right choice, with numbers from three engines.

## The nine sections

| # | Section | Fixed question |
| - | ------- | -------------- |
| 01 | [Why it exists](01_why/) | What problem was this built for, and what does it give up? |
| 02 | [Install & verify](02_install/) | Can I run it and prove it's running? |
| 03 | [Connect three ways](03_connect/) | The same "hello" query from the CLI, QueryMux, and Python. |
| 04 | [Model the data](04_model/) | How does the `store` dataset *want* to look in this engine? |
| 05 | [Load it](05_load/) | Get the generated `store` data in, reproducibly. |
| 06 | [Run the query catalog](06_queries/) | Translate Q01–Q15, or say why one can't or shouldn't be translated. |
| 07 | [Explain & measure](07_explain/) | What does the engine say it did, and how long did it take? |
| 08 | [Concurrency & load](08_concurrency/) | How does it behave under the load scenarios that apply to it? |
| 09 | [When to choose it](09_when/) | Yes or no on the standard scenarios, citing your own numbers. |
| — | [concept_answers.md](concept_answers.md) | PostgreSQL's column of the [concept map](../../reference/concept_map.md), in detail |

## Quick start

```bash
# the server (from engines/03_postgres/02_install/)
docker compose up -d

# the data (from the repo root, after SQLite's make_dbs.py)
python3 engines/03_postgres/05_load/build_postgres.py            # idx_/noidx_ at 10k, 100k, 1m
python3 engines/03_postgres/05_load/build_postgres.py --writes   # scratch copy for §8
cd engines/03_postgres/05_load && psql postgresql://student:student@localhost:5432/course -f rebuild.sql

# the measurement API on PostgreSQL (from lab/api/starter_code/)
ENGINE=postgres PORT=8003 RELOAD=0 python -m app.main
```

## Where this unit sits

- **Before:** [01_sqlite](../01_sqlite/) and [02_duckdb](../02_duckdb/).
  Almost everything here is compared with both, so keep their §7 and §8
  numbers handy.
- **Alongside:** [SQLite vs. PostgreSQL](../../reference/topics/sqlite_vs_postgres.md)
  and [Users, roles, and schemas](../../reference/topics/users_roles_schemas.md).
- **After:** [04_mongodb](../04_mongodb/), and the
  [distributed track](../../tracks/distributed/), which puts a replica next to
  this server.
