# 04 — MongoDB

Document store · client/server · flexible schema

MongoDB is the first engine in the field guide that isn't relational. There
are no tables, no rows, and no SQL. A database holds **collections** of
**documents**: JSON-like records that can nest other records and lists inside
them, and that don't have to match each other. Instead of splitting a purchase
across eight tables and joining it back together, you store it the way your
program reads it.

That one change moves a lot of decisions from the database to you: what
goes inside what, what gets copied, and what keeps references straight.

**You'll come out of this unit able to:**

- run MongoDB in Docker and query it from `mongosh` and Python;
- decide what to embed and what to reference, and measure what each costs;
- write the query catalog as `find` and aggregation pipelines;
- read `explain("executionStats")` and say why a query is fast or slow;
- measure what write concern, hot documents, and transactions cost;
- decide when a document store is the right choice, with numbers from four engines.

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
| — | [concept_answers.md](concept_answers.md) | MongoDB's column of the [concept map](../../reference/concept_map.md), in detail |
| — | [pymongo_walkthrough.md](pymongo_walkthrough.md) | Handout: PyMongo from `find_one` to grouping, sorting, and aggregation pipelines, on `idx_10k` |

## Quick start

```bash
# the server (from engines/04_mongodb/02_install/)
docker compose up -d

# the data (from the repo root, after SQLite's make_dbs.py)
python3 engines/04_mongodb/05_load/build_mongo.py            # idx_/noidx_ at 10k, 100k, 1m
python3 engines/04_mongodb/05_load/build_mongo.py --writes   # scratch copy for §8
python3 engines/04_mongodb/05_load/load_classroom.py         # the 1k classroom database

# the measurement API on MongoDB (from lab/api/starter_code/)
ENGINE=mongodb PORT=8004 RELOAD=0 python -m app.main
```

## Where this unit sits

- **Before:** the three relational units. Everything here is compared with
  them, especially [03_postgres](../03_postgres/), the other server.
- **Alongside:** the [patterns](../../reference/patterns/) pages each have a
  MongoDB section, and [Concurrency and locking](../../reference/topics/concurrency_and_locking.md).
- **After:** [05_redis](../05_redis/), and the
  [distributed track](../../tracks/distributed/), where this one-member
  replica set grows to three.
