# 01 — Why it exists: DuckDB

> **Fixed question:** What problem was this built for, and what does it give up?
>
> **Student artifact:** One paragraph, plus your predictions (below)

## The problem DuckDB solves

Two kinds of database work look nothing alike:

| | **Transactions** (OLTP) | **Analytics** (OLAP) |
| - | ----------------------- | -------------------- |
| Typical question | "Show customer 7." "Record this purchase." | "Revenue by state and month, for two years." |
| Rows touched per query | one, or a handful | thousands to billions |
| Columns touched | all of them, for those few rows | a few, for all those rows |
| How often | constantly, many users at once | now and then, by analysts and reports |
| Built for it | SQLite, PostgreSQL, MySQL | DuckDB, ClickHouse, Snowflake, BigQuery |

SQLite is built for the left column. For years, the right column meant a
data warehouse: a server, a cluster, a bill, an administrator. Or it meant
loading everything into pandas and hoping it fit in memory.

DuckDB's pitch is **"SQLite for analytics"**: the right-hand column, with the
left-hand column's simplicity. It's a library in your program and a single
file, and it's built from the ground up to scan, join, and aggregate millions
of rows fast. It came out of database research at CWI in Amsterdam (the
institute where Python was created) in 2019.

## The mental model: same box as SQLite, different shelves

```
┌──────────────────────── your Python process ────────────────────────┐
│   route ──► duckdb module ──► DuckDB engine (C++ library, all cores) │
└──────────────────────────────────────┼──────────────────────────────┘
                                       ▼
                         store.duckdb   (one file, + .wal while writing)
```

From the outside it's SQLite: no server, open a file, run SQL. The
difference is how the rows sit inside that file.

**SQLite stores rows.** Each row's values sit together:

```
[7 | 1 | 42 | Games | 9.99 | 2025-03-01]  [8 | 3 | 17 | Books | 24.50 | 2025-03-01]  ...
```

To total `amount`, it reads every whole row and uses one value from each.

**DuckDB stores columns.** Each column's values sit together, in blocks:

```
purchase_id:    7, 8, 9, 10, ...
department:     Games, Books, Games, Toys, ...
amount:         9.99, 24.50, 12.00, 5.25, ...
purchase_date:  2025-03-01, 2025-03-01, 2025-03-02, ...
```

To total `amount`, it reads **only the `amount` column**.

## Why that's fast: four motivations

1. **Read only the columns you need.** A report that uses 3 of 7 columns
   reads about 3/7 of the data. A row store always reads the whole row.
2. **Columns compress well.** A column holds one kind of value, often
   repeated: 22 departments across a million rows, dates in order. DuckDB
   stores them as small codes or runs, so there's less to read from disk and
   more fits in memory.
3. **Vectorized execution.** Instead of handling one row at a time, each
   operator processes a **vector** of about 2,048 values per step, in tight
   loops modern CPUs run very fast.
4. **Every core.** DuckDB splits a big scan across all your CPU cores
   automatically. SQLite runs a query on one.

And two motivations that have nothing to do with speed:

5. **Query files where they sit.** `SELECT … FROM 'people.csv'` works with no
   load step, and so do Parquet and JSON files, and even SQLite databases.
   For a data analyst, this alone is the reason to use it.
6. **It fits the Python data stack.** Query a pandas or Polars DataFrame with
   SQL, or get results back as one, without copying everything through
   Python objects.

## What it gives up

| Trade-off | Consequence |
| --------- | ----------- |
| **Built for many rows, not one** | Fetching a single row by its key has a fixed cost per query. A row store answers lookups faster. |
| **One process may write** | One program at a time can open the file for writing. A web server with several worker processes can't all write to it. You'll measure this in [§8](../08_concurrency/). |
| **Small writes are its weak spot** | Inserting rows one at a time, each in its own transaction, is slow. It's built for loading in bulk. |
| **Indexes don't do what you expect** | It has them, for keys and lookups, but most queries never use them. It skips data a different way ([§7](../07_explain/)). |
| **No users, roles, or `GRANT`** | Same as SQLite: access is file permissions. |
| **Younger** | First release 2019, stable file format since 1.0 (2024). SQLite dates from 2000. |

## Your artifact

1. Write one paragraph: *what DuckDB is for, and the one situation where
   you'd still pick SQLite over it.*
2. **Predict, before you measure anything.** For each catalog query group,
   will DuckDB be faster, slower, or about the same as SQLite (indexed, at
   1m)? Keep this; [§7](../07_explain/) checks it.

| Queries | What they do | DuckDB vs. SQLite: your prediction |
| ------- | ------------ | ---------------------------------- |
| Q01, Q02 | fetch one customer; one page of products | SQlite is faster barely |
| Q03, Q04, Q05, Q06 | a date range; one customer's history; a count; streaks | Duck DB |
| Q07–Q10 | leaderboard, anti-join, revenue by state, top products | Duck DB |
| Q13, Q14 | whole-history reports | Duckdb |
| Q15 | insert one purchase | SQLite |

Then read DuckDB's column of the [concept map](../../../reference/concept_map.md) and
[concept_answers.md](../concept_answers.md).
