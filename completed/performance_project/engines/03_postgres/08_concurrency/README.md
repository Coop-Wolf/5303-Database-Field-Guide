# 08 — Concurrency & load: PostgreSQL

> **Fixed question:** How does it behave under the load scenarios that apply to it?
>
> **Student artifact:** Results tables from four experiments, the exact error
> texts, and answers

## The one rule

**PostgreSQL locks rows, not files, and only writers wait, only for each
other, only on the same row.**

- Readers never wait for writers, and writers never wait for readers (MVCC:
  [§1](../01_why/#how-many-writers-at-once-mvcc)).
- Two transactions writing **different** rows never wait for each other, no
  matter how many processes they come from.
- A transaction that wants a row another one has changed but not yet
  committed **waits**, as long as it takes. There's no timeout by default.
- If two transactions each wait for a row the other holds, that's a
  **deadlock**: PostgreSQL notices within `deadlock_timeout` (1 s) and
  cancels one of them.

Set that beside the other two engines:

| | SQLite | DuckDB | PostgreSQL |
| - | ------ | ------ | ---------- |
| What's locked | the whole file, per write transaction | the whole file, per process | **one row** |
| Writers from many processes | take turns | only one process may write at all | all at once |
| A blocked writer | waits up to `busy_timeout`, then `database is locked` | fails at once | **waits** for the row |
| Readers during a write | continue (WAL) | blocked across processes | continue |

So the interesting failures move. Here nothing says "locked". The danger is
the opposite: everyone gets in, so **two clients can update the same row
from stale information**, and the database will happily let them. Experiment
2 is about exactly that.

---

## 1. The knobs

| Knob | Where | Effect |
| ---- | ----- | ------ |
| `POOL_MAX` | env var for the API (default 10) | Connections each API worker process may hold |
| Server worker processes | `uvicorn --workers 4` | More processes, each with its own pool |
| `SYNCHRONOUS_COMMIT` | env var for the API → `SET synchronous_commit` | `on`: COMMIT waits for the WAL to reach disk. `off`: COMMIT returns at once; a crash can lose the last fraction of a second of commits (never corrupt the database) |
| Isolation level | `SET TRANSACTION ISOLATION LEVEL …` | `READ COMMITTED` (default) or `REPEATABLE READ` / `SERIALIZABLE`: see experiment 2 |
| `deadlock_timeout`, `lock_timeout` | `SET …` per session | How soon deadlocks are checked; how long a lock wait may last (0 = forever) |

---

## 2. The experiments

All four write only into the `writes` schema. Build it once:

```bash
python3 engines/03_postgres/05_load/build_postgres.py --writes
```

### Experiment 1: the load scenarios, through the API

Work from [lab/api/starter_code/](../../../lab/api/starter_code/README.md)
with its `.venv` active and your Q15 route in `main.py`. For each run, stop
the API, start it as shown, and fire the load:

| Run | Start the API with | What changes |
| --- | ------------------ | ------------ |
| A | `ENGINE=postgres PORT=8003 RELOAD=0 python -m app.main` | one process, 10 connections |
| B | `ENGINE=postgres uvicorn app.main:app --port 8003 --workers 4` | **four processes**: the run that broke SQLite and DuckDB |
| C | `ENGINE=postgres SYNCHRONOUS_COMMIT=off PORT=8003 RELOAD=0 python -m app.main` | COMMIT doesn't wait for the disk |
| D | `ENGINE=postgres POOL_MAX=1 PORT=8003 RELOAD=0 python -m app.main` | one connection for everyone |

S2 (write-heavy) for every run:

```bash
python ../../loadtest/loadtest.py --base http://127.0.0.1:8003 --method POST --path "/purchases?db=writes" --n 200
python ../../loadtest/loadtest.py --base http://127.0.0.1:8003 --method POST --path "/purchases?db=writes" --n 500
```

Then, with run A's settings: S4 (mixed), and run E (the same 500 purchases
batched, as in SQLite and DuckDB):

```bash
python ../../loadtest/loadtest.py --base http://127.0.0.1:8003 --n 500 \
    --path "/customers?customer_id=7&db=writes" --write-share 0.1 --write-path "/purchases?db=writes"
python ../../loadtest/loadtest.py --base http://127.0.0.1:8003 --method POST --path "/purchases/fast?db=writes" --n 20 --batch 25
```

> **Predict before run B:** with four processes writing, how many of the 500
> writes will succeed? And before C and D: faster than A, slower, or the
> same?

| Run | Scenario | n | succeeded | failed | seconds | succeeded/sec | p95 ms | example error |
| --- | -------- | - | --------- | ------ | ------- | ------------- | ------ | ------------- |

Then check the summary table, the same as in SQLite:

```sql
SELECT count(*) FROM writes.purchases;  SELECT sum(num_purchases) FROM writes.monthly_sales;
```

### Experiment 2: the hot row

Many clients selling the **same product** at once. [hot_row.py](hot_row.py)
gives one product a stock count, starts 8 threads with a connection each, and
has every thread sell units one at a time, four different ways:

| Strategy | One sale is |
| -------- | ----------- |
| `naive` | read `on_hand`; compute `on_hand - 1` in Python; write that number back |
| `atomic` | `UPDATE stock SET on_hand = on_hand - 1` (one statement) |
| `for_update` | `SELECT … FOR UPDATE` (lock the row), then write |
| `repeatable_read` | `naive`, in a `REPEATABLE READ` transaction, retried whenever PostgreSQL refuses it |

Every strategy makes exactly as many sales as there were units, so
`on_hand after` should be 0.

```bash
cd engines/03_postgres/08_concurrency
python3 hot_row.py --workers 1 --sales 1600       # one client: the control
python3 hot_row.py                                # 8 clients
```

> **Predict for each strategy, before the 8-client run:** will `on_hand
> after` be 0? If not, roughly how far off? Which strategy will be fastest?

| Strategy | Your prediction | on_hand after | retries | sales/sec |
| -------- | --------------- | ------------- | ------- | --------- |
| naive | | | | |
| atomic | | | | |
| for_update | | | | |
| repeatable_read | | | | |

Copy the exact error text the script prints for `repeatable_read`.

### Experiment 3: watch a lock wait, then cause a deadlock

Open **two** terminals, each running
`psql postgresql://student:student@localhost:5432/course`. Run the steps in
order, switching terminals as shown. (Experiment 2 created `writes.stock`
with product 1; the first line adds product 2.)

| Step | Terminal 1 | Terminal 2 |
| ---- | ---------- | ---------- |
| 1 | `INSERT INTO writes.stock VALUES (2, 10) ON CONFLICT DO NOTHING;` | |
| 2 | `BEGIN;` `UPDATE writes.stock SET on_hand = on_hand - 1 WHERE product_id = 1;` | |
| 3 | | `BEGIN;` `UPDATE writes.stock SET on_hand = on_hand - 1 WHERE product_id = 1;` (what happens?) |
| 4 | `SELECT pid, wait_event_type, wait_event, state, query FROM pg_stat_activity WHERE datname = 'course';` | |
| 5 | `COMMIT;` | (what happens now?) `COMMIT;` |
| 6 | `BEGIN;` `UPDATE writes.stock SET on_hand = on_hand WHERE product_id = 1;` | `BEGIN;` `UPDATE writes.stock SET on_hand = on_hand WHERE product_id = 2;` |
| 7 | `UPDATE writes.stock SET on_hand = on_hand WHERE product_id = 2;` | |
| 8 | | `UPDATE writes.stock SET on_hand = on_hand WHERE product_id = 1;` |
| 9 | `COMMIT;` | `COMMIT;` |

Record what each terminal printed at steps 3, 5, 7, and 8, and the exact
error text.

### Experiment 4: what a COMMIT costs

Experiment 1 runs through HTTP, and the API itself has limits. To see the
database's own numbers, [commit_cost.py](commit_cost.py) inserts straight
into `writes` and varies three things: `synchronous_commit`, the number of
connections, and rows per commit:

```bash
python3 commit_cost.py
```

> **Predict:** which of the three changes commits per second most? Rows per
> second?

---

## 3. Questions to answer

1. In experiment 1, compare run B with the same four-process run in SQLite
   and DuckDB. What does PostgreSQL do differently that explains the result?
2. Did runs C and D change throughput through the API? Compare with what
   `commit_cost.py` measured directly, then explain the difference. (Fairness
   rule 11 is a hint.)
3. Explain the `naive` result in experiment 2: describe, step by step, how
   two clients lose a sale between them. Why did the 1-client control lose
   nothing?
4. `atomic`, `for_update`, and `repeatable_read` all came out right. How does
   each one prevent the lost update, and what does each cost? When could you
   **not** use `atomic`?
5. In experiment 3, what did terminal 2 wait for at step 3, and why did one
   terminal get an error at step 8 instead of waiting forever? Which one, and
   what happened to its first update?

## Going deeper

- [Concurrency and locking](../../../reference/topics/concurrency_and_locking.md):
  the same questions across all five engines.
- [Replication and caching](../../../reference/topics/replication_and_caching.md):
  copies of the data help reads; the [distributed track](../../../tracks/distributed/)
  measures PostgreSQL primary/replica lag and failover.
- PostgreSQL docs: [Transaction isolation](https://www.postgresql.org/docs/current/transaction-iso.html)
  and [Explicit locking](https://www.postgresql.org/docs/current/explicit-locking.html).

## Your artifact

The filled-in tables from experiments 1, 2, and 4; what each terminal
printed in experiment 3; the **exact** text of every error you saw; and short
answers to the five questions, each citing a number from your tables.
