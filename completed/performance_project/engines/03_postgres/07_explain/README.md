# 07 — Explain & measure: PostgreSQL

> **Fixed question:** What does the engine say it did, and how long did it take?
>
> **Student artifact:** `driver.py` results for all three engines, plan
> summaries, your [§1](../01_why/) predictions checked, and answers

Same [measurement ladder](../../../lab/measurement_ladder.md): **look** (right
rows?), **ask** (what's the plan?), **time** (three sizes, with and without
indexes). Now every number has two twins: SQLite and DuckDB, same rows, same
queries.

---

## 1. Start the API on PostgreSQL

The routes don't change; the harness does.
[app/experiment_postgres.py](../../../lab/api/starter_code/app/experiment_postgres.py)
takes over when `ENGINE=postgres` is set. From
[lab/api/starter_code/](../../../lab/api/starter_code/README.md) with its
`.venv` active:

```bash
pip install -e ".[dev]"                                    # picks up psycopg if you installed before it was added
ENGINE=postgres PORT=8003 RELOAD=0 python -m app.main      # leave this running
python driver.py --base http://127.0.0.1:8003 --out results_postgres
```

You need the other two engines' results as well: SQLite's from its §7
(`results_sqlite/`, or rerun on port 8001), and DuckDB's (`results_duckdb/`,
port 8002).

> **One pool, opened once.** The SQLite harness opens the file per request.
> Here, each API process opens a **pool** of connections the first time it's
> needed and keeps them. Connecting to a server takes milliseconds (a network
> round trip, a password check, a new server process); per request, you'd be
> timing that instead of the query. `POOL_MAX` (default 10) sets the pool size.

---

## 2. How PostgreSQL finds rows

A table is a **heap**: pages of row versions in no particular order. Every
row version has a physical address, its **TID**: (page, slot).

An **index** is a separate B-tree, sorted by the indexed columns, whose
entries point to TIDs. That's SQLite's design, with two differences that
explain most of this section:

- **The index doesn't know whether a row is visible to you.** Because of
  MVCC, the heap holds old versions too; only the heap says which version
  your transaction may see. So an index scan normally visits the heap for
  **every** match, even when the index holds every column the query needs.
- **Unless the visibility map says the page is clean.** VACUUM marks pages
  where every row is visible to everyone. On those pages an **index-only
  scan** can skip the heap. The plan counts the visits it couldn't skip as
  `Heap Fetches`.

| Operation | What happens | Cost |
| --------- | ------------ | ---- |
| **Index Scan** | Walk the index; for each match, fetch its heap page | per match, in index order: random I/O |
| **Index Only Scan** | Walk the index; visit the heap only for pages not marked all-visible | per match, mostly index pages |
| **Bitmap Index Scan + Bitmap Heap Scan** | Collect every matching TID first, sort them by page, then read each heap page **once, in order** | between an index scan and a seq scan; good for "many, but not most" |
| **Seq Scan** | Read every heap page in order | the table |
| **Parallel Seq Scan** | Several processes split the pages; a **Gather** node merges their output | the table ÷ workers, plus startup |
| **Sort**, **Incremental Sort** | Sort rows, all at once or in groups already partly ordered | rows in |
| **Hash Join** / **Hash Aggregate** | Build a hash table from one input, probe it with the other | both inputs, once |

---

## 3. Reading `EXPLAIN (ANALYZE, BUFFERS)`: the decoder

```
course=# SET search_path TO idx_1m;
course=# EXPLAIN (ANALYZE, BUFFERS) SELECT ... ;
```

The API's `plan` field is exactly this output. So is
`run_query.py ... --analyze`. Read the tree from the **innermost**
(most indented) line outward: that's where rows come from.

```
Limit  (cost=0.42..12.9 rows=50 width=27) (actual time=0.02..0.05 rows=50.00 loops=1)
       └ planner's estimate ────────────┘ └ what really happened ─────────────────┘
```

| You see | It means |
| ------- | -------- |
| `cost=A..B rows=N` | The planner's **estimate**: startup..total cost (arbitrary units), and the rows it expected |
| `actual time=A..B rows=N loops=L` | Reality, **per loop**: milliseconds to the first row..last row, rows per loop. Total rows = rows × loops |
| estimate rows ≫ or ≪ actual rows | The planner guessed wrong. Stale statistics (run `ANALYZE`) or a correlation it can't see |
| `Buffers: shared hit=H read=R` | Pages found in PostgreSQL's cache (hit) vs. fetched from the OS (read) |
| `Heap Fetches: N` | Heap visits an index-only scan couldn't skip (pages not marked all-visible) |
| `Index Searches: N` | How many times the index was descended. More than 1 on a simple filter means a **skip scan** (new in PostgreSQL 18) |
| `Workers Planned: 2, Workers Launched: 2` | Parallel query: extra processes sharing the work under a `Gather` |
| `Sort Method: quicksort Memory: 25kB` | Sorted in memory. `external merge Disk: …` means it spilled to disk: raise `work_mem` or avoid the sort |
| `Hash … Anti Join` / `Semi Join` | `NOT EXISTS` / `EXISTS`, done as one hash join instead of a loop |
| `SubPlan` | A subquery re-run per outer row (`hashed SubPlan` means it was turned into a hash lookup) |
| `Memoize` | A cache in front of a repeated inner lookup |
| `Planning Time`, `Execution Time` | Time inside the server only. **Not** the network round trip |

**Red flags:** a `Seq Scan` on a big table that returns a few rows; an
estimate off by 100× or more; `Sort Method: external merge`; a `SubPlan` or
`Nested Loop` with `loops=` in the thousands over a big table; large
`Heap Fetches` on an index-only scan.

### Three questions the plans answer

One worked example, then two for you.

**1. Where does the rest of the time go?**

Run Q01 through the API and look at both numbers in the envelope:

```bash
curl -s "http://127.0.0.1:8003/customers?customer_id=7&db=idx_1m" | python3 -m json.tool
```

> **Predict:** the plan's last line says `Execution Time`. Will `elapsed_ms`
> be about the same, a little more, or many times more?

<details>
<summary>Answer</summary>

Many times more. On one measurement: `Execution Time: 0.007 ms` in the plan,
`elapsed_ms: 0.137` in the envelope, so 95% of the time was outside the
query.

`Execution Time` is the server's own work: find one customer by primary key,
join one zipcode. `elapsed_ms` is what your program waits: send the SQL over
the connection, the server parses and plans it, does the work, sends the row
back, and psycopg turns it into Python values. For a query this small, the
**round trip is the cost**. SQLite and DuckDB never pay it, because there's
no connection: the engine is inside your program.

The method: for small queries, compare `elapsed_ms` across engines; for big
ones, `Execution Time` tells you how much was the database itself.

</details>

**2. What does `Heap Fetches` count?** Q05 answers this. In `idx_1m` its plan
is an `Index Only Scan` with `Heap Fetches: 0`. Now do this in `writes`:

```bash
cd engines/03_postgres/06_queries
python3 run_query.py q05.sql department=Games --db writes --analyze      # note Heap Fetches
psql postgresql://student:student@localhost:5432/course -c \
  "INSERT INTO writes.purchases (customer_id, card_id, product_id, department, amount, purchase_date)
   SELECT 1, 1, 1, 'Games', 9.99, '2026-01-15' FROM generate_series(1, 5000)"
python3 run_query.py q05.sql department=Games --db writes --analyze      # again, right away
psql postgresql://student:student@localhost:5432/course -c "VACUUM writes.purchases"
python3 run_query.py q05.sql department=Games --db writes --analyze      # and after VACUUM
```

Predict each `Heap Fetches` number before you run it, then explain all three.
(If the first one isn't 0, autovacuum hasn't caught up yet. That's part of
the answer.)

**3. How much of a report's speed comes from parallel workers?** Q09 answers
this:

```bash
python3 run_query.py q09.sql --db idx_1m --runs 5
python3 run_query.py q09.sql --db idx_1m --runs 5 --workers 0
```

Compare both with SQLite's Q09 and with DuckDB's on one thread
([DuckDB §7](../../02_duckdb/07_explain/README.md#three-questions-the-plans-answer)).
Of the three engines on one core, which is fastest, and what does that say
about where each one's speed comes from?

---

## 4. Measuring

The driver's `elapsed_ms` is the same measurement in every engine:
`execute()` plus `fetchall()`, median of 5. See
[fairness](../../../lab/fairness.md) for what isn't equal: PostgreSQL runs in
Docker (rule 8) and pays a network round trip that the library engines
don't. Name both in your FINDINGS.

### Check your §1 predictions

Bring the table you filled in [§1](../01_why/). Add the `idx_1m` numbers:

| Queries | Your §1 prediction | SQLite (ms) | DuckDB (ms) | PostgreSQL (ms) |
| ------- | ------------------ | ----------: | ----------: | --------------: |
| Q01, Q02 | | | | |
| Q03–Q06 | | | | |
| Q08 (and noidx_1m) | | | | |
| Q09, Q10, Q13 | | | | |
| Q15, 4 workers | | (§8) | (§8) | (§8) |

### Predict before your first PostgreSQL driver run

| Queries | Your prediction: how much faster is `idx_*` than `noidx_*` at 1m? | What happened (cite a number) |
| ------- | ------------------------------------------------------------------ | ----------------------------- |
| Q01, Q02 | | |
| Q03–Q06 | | |
| Q07–Q10 | | |
| Q11–Q14, slow versions | | |
| Q11–Q14, `/fast` versions | | |

Compare your answers with the same table in
[SQLite §7](../../01_sqlite/07_explain/README.md#predict-before-you-run-the-driver).
Where does PostgreSQL disagree with SQLite about whether an index helps, and
which plan line explains it?

---

## 5. Diagnosing a slow query in PostgreSQL

The method is SQLite's: get the plan (here, `EXPLAIN (ANALYZE, BUFFERS)`),
find the node whose rows or time grow with the table, and measure at two
sizes. PostgreSQL gives you more levers:

| Fix | In PostgreSQL | Examples |
| --- | ------------- | -------- |
| **Index** | B-tree, plus covering (`INCLUDE`), partial (`WHERE`), and expression indexes | `(customer_id) INCLUDE (amount)`; `ON purchases (purchase_date) WHERE amount > 100` |
| **Statistics** | The planner is only as good as its numbers | `ANALYZE`; check the estimate vs. actual rows first |
| **Rewrite** | Same as SQLite | keyset instead of `OFFSET`; `NOT EXISTS` instead of `NOT IN` |
| **Precompute** | Summary tables, or **materialized views** | `CREATE MATERIALIZED VIEW … ; REFRESH MATERIALIZED VIEW …` |
| **Settings** | Per session or per server | `work_mem` for sorts and hashes; `max_parallel_workers_per_gather` |
| **Change the contract** / **Accept it** | Same as SQLite | |

### Try one: `INCLUDE` vs. a wider key

[indexes.sql](../05_load/indexes.sql) builds SQLite's covering index the
SQLite way: `(customer_id, amount)`. PostgreSQL can also write
`(customer_id) INCLUDE (amount)`: `amount` is stored in the index but isn't
part of its sort order. In `writes`:

```sql
SET search_path TO writes;
CREATE INDEX cust_include ON purchases (customer_id) INCLUDE (amount);
VACUUM ANALYZE purchases;
-- compare the two indexes' sizes:
SELECT indexrelname, pg_size_pretty(pg_relation_size(indexrelid))
FROM pg_stat_user_indexes WHERE schemaname = 'writes';
```

Then compare the plans of these two queries, first with both indexes, then
after `DROP INDEX idx_purchases_cust_amount`:

```sql
EXPLAIN (ANALYZE) SELECT sum(amount) FROM purchases WHERE customer_id = 42;
EXPLAIN (ANALYZE) SELECT amount FROM purchases WHERE customer_id = 42 ORDER BY amount DESC LIMIT 5;
```

**Predict first:** which index is smaller, and can both answer both queries
without a Sort? Put `idx_purchases_cust_amount` back
(`CREATE INDEX idx_purchases_cust_amount ON purchases (customer_id, amount);`)
when you're done.

## Your artifact

1. `results_postgres/results.md` from a full driver run, beside the SQLite
   and DuckDB results.
2. A plan summary for each query: the one or two plan lines that explain its
   time. Describe *how PostgreSQL runs it*, not what the query does.
3. Your §1 prediction table and the idx-vs-noidx table from §4, completed,
   and the plan line behind each place PostgreSQL disagreed with SQLite.
4. An answer to each query's **Think about it** prompt in
   [06_queries/](../06_queries/README.md), to questions 2 and 3 in §3, and to
   the `INCLUDE` experiment. Each answer cites a number or a plan line.
