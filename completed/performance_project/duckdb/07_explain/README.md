# 07 — Explain & measure: DuckDB

> **Fixed question:** What does the engine say it did, and how long did it take?
>
> **Student artifact:** `driver.py` results for both engines, plan summaries,
> your [§1](../01_why/) predictions checked, and answers

Same [measurement ladder](../../../lab/measurement_ladder.md) as SQLite:
**look** (right rows?), **ask** (what's the plan?), **time** (how long, at
three sizes, with and without indexes?). This time every number has a twin:
the same query, on the same rows, in SQLite.

---

## 1. Start the API on DuckDB

The routes don't change. The harness does:
[app/experiment_duckdb.py](../../../lab/api/starter_code/app/experiment_duckdb.py)
replaces [app/experiment.py](../../../lab/api/starter_code/app/experiment.py)
when the API starts with `ENGINE=duckdb`.

You'll use **three terminals**: one SQLite API, one DuckDB API, and one for
the driver. Environment variables are read once, by the program that starts
with them, so each terminal gets only what its own program needs. (The full
table of who reads what is in
[starter_code/](../../../lab/api/starter_code/README.md#environment-variables).)

**Step 0, once.** `DATA_DIR` should already be in your shell profile from
the SQLite unit (`export DATA_DIR="$HOME/5303_data/sqlite"`). The DuckDB files
go in the `duckdb/` folder next to it unless you set `DUCKDB_DIR`. Build
them ([§5](../05_load/)), then make sure the venv has the `duckdb` package:

```bash
python3 engines/02_duckdb/05_load/build_duckdb.py         # from the repo root

cd lab/api/starter_code && source .venv/bin/activate
pip install -e ".[dev]"                                   # picks up duckdb if you installed before it was added
```

**Terminal 1: SQLite**, as in the SQLite unit. No `ENGINE` means SQLite, and
no `PORT` means 8001:

```bash
cd lab/api/starter_code && source .venv/bin/activate
RELOAD=0 python -m app.main                               # port 8001
```

**Terminal 2: DuckDB.** The same command with two more settings in front.
They apply to this one command only:

```bash
cd lab/api/starter_code && source .venv/bin/activate
ENGINE=duckdb PORT=8002 RELOAD=0 python -m app.main       # port 8002
```

Check that it took: <http://127.0.0.1:8002/docs> should say **(duckdb)** in
the title, and every response should include `"engine": "duckdb"`. If it says
sqlite, the `ENGINE=` didn't reach this process. Stop it with Ctrl-C and
start it again; a running API can't change engines.

Using your own copy of `main.py` from the SQLite unit? Copy the `ENGINE`
block near the top of the starter's
[main.py](../../../lab/api/starter_code/app/main.py) into yours. Your Q03, Q08,
and Q15 routes need no changes.

**Terminal 3: the driver.** It sets no variables. It doesn't read `ENGINE`;
`--base` decides which API it measures. Check both with 10k first, then do
the full runs:

```bash
cd lab/api/starter_code && source .venv/bin/activate
python driver.py --base http://127.0.0.1:8001 --out results_sqlite --sizes 10k
python driver.py --base http://127.0.0.1:8002 --out results_duckdb --sizes 10k

python driver.py --base http://127.0.0.1:8001 --out results_sqlite
python driver.py --base http://127.0.0.1:8002 --out results_duckdb
```

The results land in `starter_code/results_sqlite/` and
`starter_code/results_duckdb/`.

| Message | Cause |
| ------- | ----- |
| driver: `idx_1m.db not found` | The driver reads the **SQLite** files to choose some parameters, even for DuckDB. `DATA_DIR` is wrong or missing in terminal 3 |
| API: `idx_1m.duckdb not found in ...` | The DuckDB files aren't where the API looked. Run `build_duckdb.py`, or set the same `DUCKDB_DIR` you built with |
| `Could not set lock on file` | Another process holds the file for writing: a second API, or a `duckdb` shell open on `writes` |
| driver: `API not reachable` | That port's API isn't running, or `--base` has the wrong port |

> **DuckDB keeps files open.** The SQLite harness opens the file on every
> request. Opening a DuckDB file takes milliseconds, not microseconds, so the
> DuckDB harness opens each file once and keeps it open. The experiment
> databases open **read-only**, so you can still open them in the DuckDB shell
> with `-readonly` while the API runs. To rebuild them, stop the API first.

---

## 2. How DuckDB finds rows

Forget B-trees for a moment. Everything here is a **scan**; the question is
how much of it gets skipped.

```
purchases (1,000,000 rows)
┌─ row group 0: rows 0–122,879 ──────────────────────────────────┐
│  purchase_id    [min …, max …]   compressed, read on its own   │
│  department     [min …, max …]   compressed, read on its own   │
│  amount         [min …, max …]   compressed, read on its own   │
│  purchase_date  [min …, max …]   compressed, read on its own   │
│  ...                                                           │
└────────────────────────────────────────────────────────────────┘
┌─ row group 1: rows 122,880–245,759 ────────────────────────────┐
│  ...                                                           │
```

| Mechanism | What happens | When it helps |
| --------- | ------------ | ------------- |
| **Column projection** | Read only the columns the query names | Always. A query on 2 of 7 columns reads about 2/7 of the data |
| **Zone maps** (min/max per row group) | Skip a whole row group whose range can't match the filter | Only when matching values are **clustered** in a few row groups |
| **Vectorized execution** | Each operator handles ~2,048 values per call | Always. Less per-row overhead |
| **Parallel pipelines** | Split row groups across all CPU cores | Big scans. Tiny queries pay to start the threads |
| **ART index** | Jump straight to matching rows | Only for a filter DuckDB expects to match **very few** rows (by default about 2,048 or fewer; see `index_scan_max_count`) |
| **Dynamic filter** | `ORDER BY … LIMIT` feeds its current cutoff back into the scan, which then skips rows that can't make the top N | `TOP_N` queries |

There's no covering index and no "lookup per row." When DuckDB does use an
index, it fetches the matching rows' columns directly from their row groups.

---

## 3. Reading a DuckDB plan: the decoder

Three ways to see one:

| Command | What you get |
| ------- | ------------ |
| `EXPLAIN <query>` | The plan DuckDB *intends*, with **estimated** rows. Doesn't run the query |
| `EXPLAIN ANALYZE <query>` | Runs it, then shows the plan with **actual** rows and time per operator |
| the API's `plan` field | `EXPLAIN ANALYZE`, one line per operator, indented by depth, `PROJECTION` steps left out |

Plans are trees: read them **from the bottom up**. Scans are at the leaves,
and rows flow upward.

| Plan says | Plain English | Grows with |
| --------- | ------------- | ---------- |
| `TABLE_SCAN` / `SEQ_SCAN` `[Sequential Scan]` | read the named columns of every row group the zone maps don't rule out | **the table** (minus skipped row groups) |
| `TABLE_SCAN` `[Index Scan]` | look up matching rows in an ART index | matching rows |
| `Filters: …` on a scan | the `WHERE` was pushed into the scan; nothing above it sees rejected rows | — |
| `optional: Dynamic Filter` | a `TOP_N` above will tighten this filter as it finds rows | — |
| `HASH_JOIN [INNER]` | build a hash table from one side, probe it with the other | both inputs, once each |
| `HASH_JOIN [ANTI]`, `[RIGHT_ANTI]`, `[SEMI]`, `[MARK]` | `NOT EXISTS` / `EXISTS` / `IN`, as a hash join instead of a per-row loop | both inputs, once each |
| `DELIM_JOIN`, `DELIM_SCAN` | a correlated subquery, rewritten to run once for all outer rows | — |
| `NESTED_LOOP_JOIN`, `PIECEWISE_MERGE_JOIN` | a join with no `=` condition | **outer × inner** |
| `HASH_GROUP_BY`, `PERFECT_HASH_GROUP_BY` | `GROUP BY` into a hash table (the "perfect" one, when keys are small integers) | rows in |
| `UNGROUPED_AGGREGATE` | `count(*)`, `sum(x)` with no `GROUP BY` | rows in |
| `TOP_N` | `ORDER BY … LIMIT n`: keep only the best *n* while scanning, no full sort | rows in, cheaply |
| `ORDER_BY` | a full sort | rows in (n·log n) |
| `WINDOW` | window functions: `ROW_NUMBER()`, `RANK()` | rows in, sorted by partition |
| `STREAMING_LIMIT`, `LIMIT` | stop after *n* rows | — |

The numbers on each `EXPLAIN ANALYZE` operator:

- **scanned:** rows the scan looked at. Compare it with the table size to see
  how much the zone maps or the index skipped.
- **out:** rows passed upward.
- **time:** CPU time in that operator, **summed across threads**. It can add
  up to more than the query's elapsed time. That's parallelism, not an error.

**Red flags in DuckDB** are different from SQLite's. A full scan of a big
table is normal, and often fast. Watch instead for:

- a `NESTED_LOOP_JOIN` or `PIECEWISE_MERGE_JOIN` with two big inputs;
- an `ORDER_BY` (full sort) over many rows where a `TOP_N` would do;
- a join whose **out** is far larger than either input (a fan-out you didn't intend);
- **scanned** close to the table size when the query only wants a narrow range.

### Three questions the plans answer

One worked example, then two for you.

**1. Why does `EXPLAIN` say "Sequential Scan" when DuckDB used an index?**

Run Q04 on `idx_1m` both ways:

```bash
cd engines/02_duckdb/06_queries
python3 run_query.py q04.sql customer_id=42 --db ~/5303_data/duckdb/idx_1m.duckdb --explain
python3 run_query.py q04.sql customer_id=42 --db ~/5303_data/duckdb/idx_1m.duckdb --analyze
```

> **Predict:** will the two plans agree on how `purchases` is read?

<details>
<summary>Answer</summary>

No. `EXPLAIN` shows `Type: Sequential Scan` with `Filters: customer_id=42`.
`EXPLAIN ANALYZE` shows `Type: Index Scan` for the same operator.

DuckDB decides between the index and the scan **while the query runs**, once
it knows how many rows the filter matches. `EXPLAIN` doesn't run anything, so
it can only show the default. In SQLite the plan was fixed before the first
row was read; here part of it isn't.

The method that follows: **in DuckDB, trust `EXPLAIN ANALYZE`.** That's why
the API's `plan` field uses it.

</details>

**2. Does an index help DuckDB?** Q04, Q05, and Q06 answer this. Compare each
one's time in `idx_*` and `noidx_*` at 1m, then use the **scanned** and
**time** numbers on the scan line of each plan to explain what you see. Then
explain the `idx_1m` and `noidx_1m` file sizes the build printed in §5.

**3. How much of DuckDB's speed comes from using every core?** Q09 answers
this:

```bash
python3 run_query.py q09.sql --db ~/5303_data/duckdb/idx_1m.duckdb --runs 5
python3 run_query.py q09.sql --db ~/5303_data/duckdb/idx_1m.duckdb --runs 5 --threads 1
```

Compare both with SQLite's best time for Q09. If cores were the whole story,
one thread should bring DuckDB back down to SQLite. Does it?

---

## 4. Measuring

The API's `elapsed_ms` is the same measurement for both engines: `execute()`
plus `fetchall()`, inside the API process, median of 5. Nothing about HTTP or
JSON is in it. See [fairness](../../../lab/fairness.md) for what *isn't* equal:
DuckDB uses every core, SQLite uses one. That's part of what you're comparing,
not a flaw in the comparison.

### Check your §1 predictions

Bring the table you filled in [§1](../01_why/) before you'd measured anything.
Add the last two columns from `results_sqlite/results.md` and
`results_duckdb/results.md` (the `idx_1m` column of each):

| Queries | Your §1 prediction | SQLite idx_1m (ms) | DuckDB idx_1m (ms) |
| ------- | ------------------ | -----------------: | -----------------: |
| Q01, Q02 | | | |
| Q03, Q04, Q05, Q06 | | | |
| Q07–Q10 | | | |
| Q13, Q14 | | | |
| Q15 | | (from §8) | (from §8) |

A wrong prediction you can explain is worth more than a right one you can't.

### Predict before your first DuckDB driver run

| Queries | Your prediction: how much faster is DuckDB `idx_*` than `noidx_*` at 1m? | What happened (cite a number) |
| ------- | ------------------------------------------------------------------------ | ----------------------------- |
| Q01, Q02 | | |
| Q03–Q06 | | |
| Q07–Q10 | | |
| Q11–Q14, slow versions | | |
| Q11–Q14, `/fast` versions | | |

The [SQLite rules of thumb](../../01_sqlite/07_explain/README.md#rules-of-thumb-for-times)
for what a time means to a user still apply.

---

## 5. Diagnosing a slow query in DuckDB

The method is SQLite's: get the plan (`EXPLAIN ANALYZE`), find the operator
whose time or row count grows with the table, measure at two sizes. The fix
categories shift:

| Fix | In DuckDB | Examples |
| --- | --------- | -------- |
| **Layout**: make the zone maps skip | **The main lever.** Load or rebuild the table sorted by the column you filter on | `CREATE TABLE … AS SELECT … ORDER BY purchase_date` |
| **Rewrite**: same answer, less work | Same as SQLite | keyset instead of `OFFSET`; `QUALIFY`; `ANTI JOIN` |
| **Precompute** | Same idea, less often needed | summary table |
| **Index** | Point lookups on a key; measure before adding more (question 2 in §3) | the primary key you already have |
| **Change the contract** / **Accept it** | Same as SQLite | |

### Try the main lever: layout

Q03 asks for one week of purchases. Build a copy of `purchases` sorted by date
(outside the repo):

```bash
duckdb sorted_1m.duckdb \
  "ATTACH '~/5303_data/duckdb/noidx_1m.duckdb' AS src (READ_ONLY);
   CREATE TABLE purchases AS SELECT * FROM src.purchases ORDER BY purchase_date;
   CHECKPOINT;"
```

> **Predict:** how many rows will Q03's scan look at in the sorted copy,
> compared with `noidx_1m`?

Then check, using `--analyze` on both and reading the scan's row count:

```bash
cd engines/02_duckdb/06_queries
python3 run_query.py q03.sql start=2025-03-01 end=2025-03-08 --db ~/5303_data/duckdb/noidx_1m.duckdb --analyze
python3 run_query.py q03.sql start=2025-03-01 end=2025-03-08 --db sorted_1m.duckdb --analyze
```

(Use the full path to `sorted_1m.duckdb` if you built it elsewhere.) What did
sorting cost, and which other queries would it help or not help?

## Your artifact

1. `results_sqlite/results.md` and `results_duckdb/results.md` from full
   driver runs.
2. A plan summary for each query on DuckDB: the one or two plan lines that
   explain its time. Describe *how DuckDB runs it*, not what the query does.
3. Your §1 prediction table and the idx-vs-noidx table from §4, completed.
4. An answer to each query's **Think about it** prompt in
   [06_queries/](../06_queries/README.md), to questions 2 and 3 in §3, and to
   the layout experiment in §5. Each answer cites a number or a plan line.
