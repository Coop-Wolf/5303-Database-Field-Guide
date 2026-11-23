# 06 — Run the query catalog: DuckDB

> **Fixed question:** Translate Q01–Q15, or say why one can't or shouldn't be translated.
>
> **Student artifact:** All 19 routes answering with `ENGINE=duckdb`, and the
> translation table below filled in

Files: `qNN.sql` per query, `qNN_fast.sql` for rewrites. Routes follow the
[route contract](../../../lab/api/02_route_contract/).

Every query was ported from [SQLite's catalog](../../01_sqlite/06_queries/),
and every one fits (✓). The translations are already done; each file's header
has a DuckDB-specific **Think about it** prompt for [§7](../07_explain/).
Your job here is to **read the diffs**: what had to change, and why.

## The catalog in DuckDB

| ID  | Query                             |  Fit  | Pattern                      | File(s)                                           |
| --- | --------------------------------- | :---: | ---------------------------- | ------------------------------------------------- |
| Q01 | One customer by id                |   ✓   | plan basics                  | [q01.sql](q01.sql)                                |
| Q02 | One page of products              |   ✓   | keyset_pagination            | [q02.sql](q02.sql)                                |
| Q03 | Purchases in a date range         |   ✓   | plan basics                  | [q03.sql](q03.sql)                                |
| Q04 | A customer's purchase history     |   ✓   | plan basics                  | [q04.sql](q04.sql)                                |
| Q05 | Count purchases in one department |   ✓   | counting_and_summaries       | [q05.sql](q05.sql)                                |
| Q06 | A customer's purchase streaks     |   ✓   | gaps_and_islands             | [q06.sql](q06.sql)                                |
| Q07 | 90-day spending leaderboard       |   ✓   | window_ranking               | [q07.sql](q07.sql)                                |
| Q08 | Products never bought in a state  |   ✓   | anti_joins                   | [q08.sql](q08.sql)                                |
| Q09 | Revenue by state                  |   ✓   | plan basics                  | [q09.sql](q09.sql)                                |
| Q10 | Top 10 products by revenue        |   ✓   | plan basics                  | [q10.sql](q10.sql)                                |
| Q11 | Deep pagination: OFFSET vs keyset |   ✓   | keyset_pagination            | [q11.sql](q11.sql) · [q11_fast.sql](q11_fast.sql) |
| Q12 | Random sample                     |   ✓   | random_sampling              | [q12.sql](q12.sql) · [q12_fast.sql](q12_fast.sql) |
| Q13 | Revenue by month: scan vs summary |   ✓   | counting_and_summaries       | [q13.sql](q13.sql) · [q13_fast.sql](q13_fast.sql) |
| Q14 | State × department × month report |   ✓   | multi_cte_reports            | [q14.sql](q14.sql) · [q14_fast.sql](q14_fast.sql) |
| Q15 | Insert a purchase                 |   ✓   | — ([§8](../08_concurrency/)) | [q15.sql](q15.sql) · [q15_fast.sql](q15_fast.sql) |

## Read the diffs

Compare each DuckDB file with its SQLite twin:

```bash
cd units
diff 01_sqlite/06_queries/q06.sql 02_duckdb/06_queries/q06.sql
```

Fill in this table. The first row is done for you; every other query listed
changed in some way. For each one, the *why* is the part that counts: what
about DuckDB, or about SQLite, forced the change?

| Query    | What changed      | Why                                                                                     |
| -------- | ----------------- | --------------------------------------------------------------------------------------- |
| all      | `:name` → `$name` | Each driver's placeholder style. Python's `sqlite3` uses `:name`; `duckdb` uses `$name` |
| Q06      | `day - CAST` → `julianday`   |  Don't need julianday for duckdb                                |
| Q10      | `Group by clauses` | Duckdb requires every non-aggregated column in group by clause    |
| Q13, Q14 | `strftime()` → `substr()` |   Duckby has strftime()   |

Then answer: **which SQLite-isms from the
[SQLite list](../../01_sqlite/06_queries/README.md#sqlite-isms-to-watch-for-when-you-port-these-later)
did *not* need to change**, and why did they survive?

### Shortcuts DuckDB has that the catalog doesn't use

The catalog files stay as close to SQLite's as possible, so the two engines run
the *same* query. DuckDB has shorter ways to write several of them. Try at
least one, check that it returns the same rows, and compare its plan with the
catalog version's:

| Query | DuckDB shortcut                                    | Docs                                                                                  |
| ----- | -------------------------------------------------- | ------------------------------------------------------------------------------------- |
| Q07   | `QUALIFY rank <= 20` instead of a CTE plus `LIMIT` | [QUALIFY](https://duckdb.org/docs/stable/sql/query_syntax/qualify)                    |
| Q08   | `FROM products ANTI JOIN …`                        | [ANTI JOIN](https://duckdb.org/docs/stable/sql/query_syntax/from#semi-and-anti-joins) |
| Q12   | `FROM purchases USING SAMPLE 10 ROWS`              | [Samples](https://duckdb.org/docs/stable/sql/samples)                                 |
| Q14   | `GROUP BY CUBE (state_code, department, month)`    | [GROUPING SETS](https://duckdb.org/docs/stable/sql/query_syntax/grouping_sets)        |
| any   | `GROUP BY ALL`, `ORDER BY ALL`                     | [GROUP BY](https://duckdb.org/docs/stable/sql/query_syntax/groupby)                   |

The [patterns](../../../reference/patterns/) pages for those queries show each shortcut
in context.

## Running a query by hand

The DuckDB shell has no `.param set`, so
[run_query.py](run_query.py) binds the `$name` parameters for you:

```bash
cd engines/02_duckdb/06_queries
python3 run_query.py q01.sql customer_id=7                       # classroom database
python3 run_query.py q03.sql start=2025-03-01 end=2025-03-08 --db ~/5303_data/duckdb/idx_1m.duckdb
python3 run_query.py q04.sql customer_id=42 --db ~/5303_data/duckdb/idx_1m.duckdb --analyze
```

`--explain` prints the plan; `--analyze` runs the query and prints the plan
with real row counts and times ([§7](../07_explain/) explains how to read it).

In QueryMux or the DuckDB shell, paste the SQL and replace each `$name` with a
literal value: `$customer_id` → `7`, `$start` → `'2025-03-01'`.

## In the API

The routes don't change between engines. Only the harness does. Start the API
with `ENGINE=duckdb`, and it loads these files instead of SQLite's (see
[§7](../07_explain/#1-start-the-api-on-duckdb) for the full command). The
Q03, Q08, and Q15 routes you wrote in the SQLite unit work as they are.

## Your artifact

1. The translation table above, completed, plus your answer about which
   SQLite-isms survived.
2. Every route answering in `/docs` with `ENGINE=duckdb` against `idx_10k`,
   and every `/fast` route returning the same rows as its slow twin (Q12 is
   random, so it's the exception).
3. One DuckDB shortcut you tried: the query, proof it returns the same rows,
   and one sentence on whether its plan differs.
