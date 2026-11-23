# 02 — DuckDB

Relational · embedded · column store (analytics)

DuckDB is SQLite's closest relative and its opposite. Like SQLite, it's a
**library** inside your program, and the whole database is **one file**: no
server, no users, no Docker. Unlike SQLite, it stores data **by column**
instead of by row, and it's built to answer questions about *many* rows at
once instead of fetching *one* row fast.

Same data, same queries, one big change. This unit is about what that one
change does.

**You'll come out of this unit able to:**

- explain the difference between a row store and a column store, and predict
  which queries each one wins;
- load the `store` data three ways: from SQLite files, from a CSV, and from
  Parquet;
- read a DuckDB query plan and say why a query is fast or slow;
- measure the same catalog on SQLite and DuckDB and explain every big
  difference;
- decide when DuckDB is the right choice, and when it isn't, with your own
  numbers.

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
| — | [concept_answers.md](concept_answers.md) | DuckDB's column of the [concept map](../../reference/concept_map.md), in detail |

## Quick start

```bash
# from the repo root, after SQLite's make_dbs.py has built its databases
pip install duckdb
python3 engines/02_duckdb/05_load/build_duckdb.py      # ~5 s: idx_/noidx_ at 10k, 100k, 1m
duckdb -readonly ~/5303_data/duckdb/idx_1m.duckdb     # or datasets/store/generated/duckdb/

# the 1k classroom database, from the CSV
cd engines/02_duckdb/05_load && duckdb store_classroom.duckdb ".read rebuild.sql"

# the measurement API on DuckDB (from lab/api/starter_code/)
ENGINE=duckdb PORT=8002 RELOAD=0 python -m app.main
```

## Where this unit sits

- **Before:** [01_sqlite](../01_sqlite/). Everything here is "compared with
  SQLite," so finish its §7 first. You'll need those numbers.
- **Alongside:** [SQLite vs. DuckDB](../../reference/topics/sqlite_vs_duckdb.md), the
  two embedded engines side by side.
- **After:** [03_postgres](../03_postgres/), the first server.
