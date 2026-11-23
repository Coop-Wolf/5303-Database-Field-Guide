# 06 — Run the query catalog: PostgreSQL

> **Fixed question:** Translate Q01–Q15, or say why one can't or shouldn't be translated.
>
> **Student artifact:** All 19 routes answering with `ENGINE=postgres`, and the
> translation table below filled in

Files: `qNN.sql` per query, `qNN_fast.sql` for rewrites. Routes follow the
[route contract](../../../lab/api/02_route_contract/).

Every query was ported from [SQLite's catalog](../../01_sqlite/06_queries/),
and every one fits (✓). Each file's header has a PostgreSQL-specific **Think
about it** prompt for [§7](../07_explain/). Your job here is to **read the
diffs**: what had to change, what didn't, and why.

## The catalog in PostgreSQL

| ID | Query | Fit | Pattern | File(s) |
| -- | ----- | :-: | ------- | ------- |
| Q01 | One customer by id | ✓ | plan basics | [q01.sql](q01.sql) |
| Q02 | One page of products | ✓ | keyset_pagination | [q02.sql](q02.sql) |
| Q03 | Purchases in a date range | ✓ | plan basics | [q03.sql](q03.sql) |
| Q04 | A customer's purchase history | ✓ | plan basics | [q04.sql](q04.sql) |
| Q05 | Count purchases in one department | ✓ | counting_and_summaries | [q05.sql](q05.sql) |
| Q06 | A customer's purchase streaks | ✓ | gaps_and_islands | [q06.sql](q06.sql) |
| Q07 | 90-day spending leaderboard | ✓ | window_ranking | [q07.sql](q07.sql) |
| Q08 | Products never bought in a state | ✓ | anti_joins | [q08.sql](q08.sql) |
| Q09 | Revenue by state | ✓ | plan basics | [q09.sql](q09.sql) |
| Q10 | Top 10 products by revenue | ✓ | plan basics | [q10.sql](q10.sql) |
| Q11 | Deep pagination: OFFSET vs keyset | ✓ | keyset_pagination | [q11.sql](q11.sql) · [q11_fast.sql](q11_fast.sql) |
| Q12 | Random sample | ✓ | random_sampling | [q12.sql](q12.sql) · [q12_fast.sql](q12_fast.sql) |
| Q13 | Revenue by month: scan vs summary | ✓ | counting_and_summaries | [q13.sql](q13.sql) · [q13_fast.sql](q13_fast.sql) |
| Q14 | State × department × month report | ✓ | multi_cte_reports | [q14.sql](q14.sql) · [q14_fast.sql](q14_fast.sql) |
| Q15 | Insert a purchase | ✓ | — ([§8](../08_concurrency/)) | [q15.sql](q15.sql) · [q15_fast.sql](q15_fast.sql) |

## Read the diffs

```bash
cd engines
diff 01_sqlite/06_queries/q06.sql 03_postgres/06_queries/q06.sql
```

Fill in this table. The first row is done for you; every other query listed
changed in some way. The *why* is the part that counts.

| Query | What changed | Why |
| ----- | ------------ | --- |
| all | `:name` → `%(name)s` | Each driver's placeholder style: Python's `sqlite3` uses `:name`, `psycopg` uses `%(name)s` |
| Q06 | | |
| Q13, Q14 | | |

Then compare with [DuckDB's diffs](../../02_duckdb/06_queries/README.md#read-the-diffs).
**Q10 changed in DuckDB but not here.** PostgreSQL runs SQLite's
`GROUP BY pr.product_id` with `pr.product_name` in the `SELECT`. Why does it
allow that when DuckDB refused? (Search the PostgreSQL docs for "functional
dependency".) And which other SQLite-isms from the
[SQLite list](../../01_sqlite/06_queries/README.md#sqlite-isms-to-watch-for-when-you-port-these-later)
survived unchanged?

### Shortcuts PostgreSQL has that the catalog doesn't use

The catalog keeps each query close to SQLite's, so the engines run the
*same* query. PostgreSQL has shorter ways to write several. Try at least
one, check it returns the same rows, and compare its plan:

| Query | PostgreSQL shortcut | Docs |
| ----- | ------------------- | ---- |
| Q14 | `GROUP BY CUBE (state_code, department, month)`, or `GROUPING SETS` | [Grouping sets](https://www.postgresql.org/docs/current/queries-table-expressions.html#QUERIES-GROUPING-SETS) |
| Q12 | `FROM purchases TABLESAMPLE BERNOULLI (0.01)` | [TABLESAMPLE](https://www.postgresql.org/docs/current/sql-select.html#SQL-FROM) |
| Q04 | `DISTINCT ON (customer_id)` for "each customer's latest purchase" | [DISTINCT ON](https://www.postgresql.org/docs/current/sql-select.html#SQL-DISTINCT) |
| Q09 | `count(*) FILTER (WHERE department = 'Games')` next to the total | [Aggregate FILTER](https://www.postgresql.org/docs/current/sql-expressions.html#SYNTAX-AGGREGATES) |
| Q13 | `date_trunc('month', purchase_date)` instead of `to_char` | [date_trunc](https://www.postgresql.org/docs/current/functions-datetime.html#FUNCTIONS-DATETIME-TRUNC) |

## Running a query by hand

`psql` can't bind psycopg's `%(name)s` placeholders, so
[run_query.py](run_query.py) does it:

```bash
cd engines/03_postgres/06_queries
python3 run_query.py q01.sql customer_id=7                          # schema classroom
python3 run_query.py q03.sql start=2025-03-01 end=2025-03-08 --db idx_1m
python3 run_query.py q04.sql customer_id=20912 --db idx_1m --analyze
```

`--db` is the schema. `--explain` prints the plan; `--analyze` runs the query
and prints the plan with real row counts, times, and pages
([§7](../07_explain/) explains how to read it).

In `psql` or QueryMux, paste the SQL and replace each `%(name)s` with a
literal: `%(customer_id)s` → `7`, `%(start)s` → `'2025-03-01'`.

## In the API

The routes don't change between engines; only the harness does. Start the
API with `ENGINE=postgres` and it loads these files
([§7](../07_explain/#1-start-the-api-on-postgresql) has the full command).
Your Q03, Q08, and Q15 routes from the SQLite unit work as they are.

## Your artifact

1. The translation table, completed, plus your answers about Q10 and the
   SQLite-isms that survived.
2. Every route answering in `/docs` with `ENGINE=postgres` against
   `idx_10k`, and every `/fast` route returning the same rows as its slow
   twin (Q12 is random, so it's the exception).
3. One PostgreSQL shortcut you tried: the query, proof it returns the same
   rows, and one sentence on whether its plan differs.
