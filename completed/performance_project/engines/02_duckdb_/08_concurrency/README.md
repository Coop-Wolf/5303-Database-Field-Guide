# 08 — Concurrency & load: DuckDB

> **Fixed question:** How does it behave under the load scenarios that apply to it?
>
> **Student artifact:** Load results table + the exact error text

## The one rule

**One process at a time may open a DuckDB file for writing, and while it
does, no other process can open that file at all.**

- Any number of processes can open a file **read-only**, as long as none has
  it open for writing.
- Inside the process that has it, many connections and transactions run at
  once (MVCC, the same idea Postgres uses). Inserts don't block each other.
- Two transactions that change the **same row** don't wait: the second one
  fails immediately with `TransactionContext Error: Conflict on update!`.
- There's no `busy_timeout`. A process that can't get the file doesn't wait
  for it; it fails with `Could not set lock on file`.

Compare that with [SQLite's rule](../../01_sqlite/08_concurrency/README.md#the-one-rule):

| | SQLite | DuckDB |
| - | ------ | ------ |
| What's locked | the file, per **write transaction** | the file, per **process** that opened it for writing |
| Lock held for | one transaction (milliseconds) | as long as the process keeps the file open |
| Writers in one process | one at a time | many at once; same-row changes conflict |
| Another process reading during a write | yes (WAL) | **no** |
| A blocked writer | waits up to `busy_timeout`, then `database is locked` | fails immediately: `Could not set lock on file` |

Everything in this section follows from the first row.

---

## 1. Durability: WAL and checkpoints

DuckDB also uses a **write-ahead log**. A commit appends its changes to
`<name>.duckdb.wal`. A **checkpoint** later folds them into the main file:
automatically when the WAL grows past `checkpoint_threshold` (16 MB by
default), when the last connection closes, or when you run `CHECKPOINT`.

The same warning as SQLite applies: **don't copy just the `.duckdb` file while
a process has it open.** Recent commits may exist only in the `.wal`. Close
the file first, or use `EXPORT DATABASE` (see [§5](../05_load/)).

---

## 2. The knobs

| Knob | Where | Effect |
| ---- | ----- | ------ |
| Server worker processes | `uvicorn --workers 4` | More **processes** competing for the file |
| `threads` | `SET threads = 4` per connection | How many cores one query may use. Doesn't change who can open the file |
| `read_only` | `duckdb.connect(path, read_only=True)` | Lets many processes share a file, if none writes |
| ~~`busy_timeout`~~ | — | Doesn't exist. `BUSY_TIMEOUT_MS` is ignored with `ENGINE=duckdb` |

The DuckDB harness ([experiment_duckdb.py](../../../lab/api/starter_code/app/experiment_duckdb.py))
opens the experiment databases read-only and `writes` read-write, and keeps
each one open for the life of the process (see [§7](../07_explain/#1-start-the-api-on-duckdb)).

---

## 3. The experiment

| Scenario | Runs on DuckDB? | Why |
| -------- | :-------------: | --- |
| **S1 read-heavy** | ✓ | Read-only files can be shared by processes; worth checking that they really are |
| **S2 write-heavy** | ✓ | The one-writing-process rule in its purest form |
| S3 hot row | — | Waiting on an `UPDATE` route (see [load scenarios](../../../lab/load_scenarios.md)) |
| **S4 mixed 90/10** | ✓ | Do the reads survive when they share a file with writes? |
| S5 burst | optional | Same story as S2, louder |

### Setup

Every write goes into a scratch copy, so the experiment databases stay clean.
Use the folder your DuckDB files are in:

```bash
cp ~/5303_data/duckdb/idx_100k.duckdb ~/5303_data/duckdb/writes.duckdb
# or: cp datasets/store/generated/duckdb/idx_100k.duckdb datasets/store/generated/duckdb/writes.duckdb
```

Then work from [lab/api/starter_code/](../../../lab/api/starter_code/README.md)
with its `.venv` active and your Q15 route in `main.py`. For each run, stop
the API (stop the SQLite one too, if it's still running), start it as shown,
and fire the load. All commands use port 8002.

| Run | Start the API with | What changes |
| --- | ------------------ | ------------ |
| A | `ENGINE=duckdb PORT=8002 RELOAD=0 python -m app.main` | one process |
| B | `ENGINE=duckdb uvicorn app.main:app --port 8002 --workers 4` | four processes |

### S2: write-heavy, runs A and B

```bash
python ../../loadtest/loadtest.py --base http://127.0.0.1:8002 --method POST --path "/purchases?db=writes" --n 200
python ../../loadtest/loadtest.py --base http://127.0.0.1:8002 --method POST --path "/purchases?db=writes" --n 500
```

> **Predict before run B:** with four processes, how many of the 500 writes
> will succeed? All of them, about a quarter, or none?

### S4: mixed 90/10, runs A and B

```bash
python ../../loadtest/loadtest.py --base http://127.0.0.1:8002 --n 500 \
    --path "/customers?customer_id=7&db=writes" \
    --write-share 0.1 --write-path "/purchases?db=writes"
```

> **Predict before run B:** the reads never write anything. Will they all
> succeed?

### S1: read-heavy, run B only

Same four processes, reading a file none of them writes:

```bash
python ../../loadtest/loadtest.py --base http://127.0.0.1:8002 --n 500 --path "/stats/revenue_by_state?db=idx_1m"
```

### Record

| Run | Scenario | n | succeeded (200/201) | failed (503) | seconds | succeeded/sec | p95 ms | example error |
| --- | -------- | - | ------------------- | ------------ | ------- | ------------- | ------ | ------------- |

Take `p95 ms` from the *successes* line of the
[loadtest](../../../lab/loadtest/README.md) output, and copy one error
**exactly**, from `IO Error` (or `TransactionContext Error`) to the end of
the sentence.

### Run E: the same purchases, batched

Start the API as in run A, then send 500 purchases as 20 requests of 25:

```bash
python ../../loadtest/loadtest.py --base http://127.0.0.1:8002 --method POST --path "/purchases/fast?db=writes" --n 20 --batch 25
```

**Predict first:** compared with run A at `--n 500`, will purchases written
per second be about the same, a bit higher, or much higher? Was your answer
the same for SQLite?

| Run | requests | purchases per request | succeeded | seconds | purchases written/sec |
| --- | -------- | --------------------- | --------- | ------- | --------------------- |
| A   | 500      | 1                     |           |         |                       |
| E   | 20       | 25                    |           |         |                       |

### Then check the summary table

**Stop the API first.** Then:

```bash
duckdb -readonly ~/5303_data/duckdb/writes.duckdb \
  "SELECT count(*) FROM purchases; SELECT sum(num_purchases) FROM monthly_sales;"
```

> **Predict:** what happens if you run this while the API is still up? Try it
> once to check, and record the error.

---

## 4. Questions to answer

1. In run B, how many writes succeeded, and what was the exact error for the
   rest? Explain that number from the one rule. Why not zero, and why not all?
2. Did the reads in S4 run B all succeed? Explain using the rule and how the
   harness opens `writes`. Then explain why S1 run B behaved differently.
3. Compare DuckDB run A with your best SQLite write run (B or D in the
   SQLite unit). Which engine wrote faster from a single process? Cite both
   numbers.
4. Compare runs A and E. Where does the time go in a single-purchase write,
   and how does DuckDB's answer differ from SQLite's?
5. A web application runs four worker processes and needs to record
   purchases in DuckDB. Name **two** ways it could be built so that writes
   work, and what each one costs.

## Going deeper

- [DuckDB concurrency](https://duckdb.org/docs/stable/connect/concurrency):
  the official rules, with the same examples.
- [Concurrency and locking](../../../reference/topics/concurrency_and_locking.md): the
  same questions across all five engines.
- [SQLite vs. DuckDB](../../../reference/topics/sqlite_vs_duckdb.md): why the two
  embedded engines made opposite choices.

## Your artifact

The filled-in tables, the **exact** error text from runs B and the
summary-table check, and short answers to the five questions, each citing a
number from your tables.
