# 08 — Concurrency & load: MongoDB

> **Fixed question:** How does it behave under the load scenarios that apply to it?
>
> **Student artifact:** Results tables from four experiments, the exact error
> texts, and answers

## The one rule

**One document is the unit: a write to one document is always atomic, and
writers only ever collide on the same document.**

- Writes to **different** documents never wait for each other, from any
  number of clients.
- Two single-document writes to the **same** document take turns: MongoDB
  queues and retries them internally. Neither one fails.
- Inside a **multi-document transaction** it's different: if two
  transactions change the same document, the second one fails **at once**
  with a write conflict, and the client must retry the whole transaction.
- Every write also has a **write concern**: how sure MongoDB must be before it
  says "done". The default, `majority`, waits until the write is in the
  on-disk journal.

Set that beside the other three engines:

| | SQLite | DuckDB | PostgreSQL | MongoDB |
| - | ------ | ------ | ---------- | ------- |
| What's locked | the file, per transaction | the file, per process | one row | one document |
| Same row/document, plain writes | queue, then `database is locked` | one process only | the second waits | the second waits |
| Same row/document, two transactions | queue | the second **fails**: retry | the second waits | the second **fails**: retry |
| What makes a write durable | `synchronous` | WAL + checkpoint | `synchronous_commit` | **write concern** |

---

## 1. The knobs

| Knob | Where | Effect |
| ---- | ----- | ------ |
| `WRITE_CONCERN` | env var for the API: `majority` (default) or `1` | `majority`: acknowledged once on disk (and, with more members, on most of them). `1`: acknowledged as soon as the server has it in memory |
| `TXN_RETRY` | env var for the API: `0` (default) or `1` | Whether a batch transaction that hits a write conflict is retried (`with_transaction`) or answered with a 503 |
| `POOL_MAX` | env var (default 10) | Connections per API worker process |
| Server worker processes | `uvicorn --workers 4` | More processes writing at once |

**The counter document.** MongoDB has no auto-increment, so every Q15 first
increments `counters {_id: "purchase_id"}` to get its id (see
[q15.json](../06_queries/q15.json)). Every writer touches that **one
document**. Keep that in mind for experiment 1.

---

## 2. The experiments

All four write only into the `writes` database. Build it once:

```bash
python3 engines/04_mongodb/05_load/build_mongo.py --writes
```

### Experiment 1: the load scenarios, through the API

From [lab/api/starter_code/](../../../lab/api/starter_code/README.md) with
its `.venv` active and your Q15 route in `main.py`. For each run, stop the
API, start it as shown, and fire the load:

| Run | Start the API with | What changes |
| --- | ------------------ | ------------ |
| A | `ENGINE=mongodb PORT=8004 RELOAD=0 python -m app.main` | one process, `w: majority` |
| B | `ENGINE=mongodb uvicorn app.main:app --port 8004 --workers 4` | four processes |
| C | `ENGINE=mongodb WRITE_CONCERN=1 PORT=8004 RELOAD=0 python -m app.main` | acknowledged from memory |

S2 (write-heavy) for each:

```bash
python ../../loadtest/loadtest.py --base http://127.0.0.1:8004 --method POST --path "/purchases?db=writes" --n 200
python ../../loadtest/loadtest.py --base http://127.0.0.1:8004 --method POST --path "/purchases?db=writes" --n 500
```

Then with run A's settings, S4 (mixed):

```bash
python ../../loadtest/loadtest.py --base http://127.0.0.1:8004 --n 500 \
    --path "/customers?customer_id=7&db=writes" --write-share 0.1 --write-path "/purchases?db=writes"
```

And **run E**, the same 500 purchases batched: 20 requests of 25, each batch
in one multi-document transaction. Run it twice, restarting the API between:

| Run | Start the API with |
| --- | ------------------ |
| E | `ENGINE=mongodb PORT=8004 RELOAD=0 python -m app.main` |
| F | `ENGINE=mongodb TXN_RETRY=1 PORT=8004 RELOAD=0 python -m app.main` |

```bash
python ../../loadtest/loadtest.py --base http://127.0.0.1:8004 --method POST --path "/purchases/fast?db=writes" --n 20 --batch 25 --timeout 120
```

> **Predict before E:** in SQLite and PostgreSQL, batching was the fastest
> way to write. All 20 batches arrive at once, and each one increments the
> counter document inside its transaction. How many will succeed?

| Run | Scenario | n | succeeded | failed | seconds | succeeded/sec | purchases/sec | p95 ms | example error |
| --- | -------- | - | --------- | ------ | ------- | ------------- | ------------- | ------ | ------------- |

Then the summary collection, the same check as every engine:

```js
const w = db.getSiblingDB("writes");
w.purchases.countDocuments({});
w.monthly_sales.aggregate([{ $group: { _id: null, n: { $sum: "$num_purchases" } } }]);
```

### Experiment 2: the hot document

[hot_row.py](hot_row.py) is the MongoDB twin of PostgreSQL's: one stock
document, 8 threads selling from it, four ways:

| Strategy | One sale is |
| -------- | ----------- |
| `naive` | `find_one()`; compute `on_hand - 1` in Python; `$set` it back |
| `atomic` | `update_one({$inc: {on_hand: -1}})` |
| `find_modify` | `find_one_and_update({$inc: ...})`: atomic, and returns the new value |
| `transaction` | `naive`, inside a multi-document transaction, retried on write conflicts |

```bash
cd engines/04_mongodb/08_concurrency
python3 hot_row.py --workers 1 --sales 1600       # the control
python3 hot_row.py                                # 8 clients
```

> **Predict for each strategy:** will `on_hand after` be 0? Which is
> fastest? Compare with your predictions for PostgreSQL's version.

| Strategy | Your prediction | on_hand after | retries | sales/sec |
| -------- | --------------- | ------------- | ------- | --------- |
| naive | | | | |
| atomic | | | | |
| find_modify | | | | |
| transaction | | | | |

Copy the exact error text the script prints for `transaction`.

### Experiment 3: watch a conflict, and a wait

Two `mongosh` terminals, both connected with
`mongosh "mongodb://localhost:27017/?directConnection=true"`. Experiment 2
created `writes.stock`; step 1 adds a second document.

| Step | Terminal 1 | Terminal 2 |
| ---- | ---------- | ---------- |
| 1 | `db.getSiblingDB("writes").stock.replaceOne({_id: 2}, {_id: 2, on_hand: 10}, {upsert: true})` | |
| 2 | `s = db.getMongo().startSession(); s.startTransaction()` | |
| 3 | `s.getDatabase("writes").stock.updateOne({_id: 2}, {$inc: {on_hand: -1}})` | |
| 4 | | `t = db.getMongo().startSession(); t.startTransaction()` |
| 5 | | `t.getDatabase("writes").stock.updateOne({_id: 2}, {$inc: {on_hand: -1}})` (what happens?) |
| 6 | | `t.abortTransaction()` |
| 7 | | `db.getSiblingDB("writes").stock.updateOne({_id: 2}, {$inc: {on_hand: -1}})` (what happens?) |
| 8 | `s.commitTransaction()` | (and now?) |
| 9 | | `db.getSiblingDB("writes").stock.findOne({_id: 2})` |

Record what each terminal printed at steps 5, 7, 8, and 9.

### Experiment 4: what a durable write costs

[write_cost.py](write_cost.py) inserts straight into `writes`, with no API,
varying the write concern, the number of threads, and documents per write:

```bash
python3 write_cost.py
```

> **Predict:** how much faster is `{w: 1, j: false}` than `{w: "majority"}`
> for one thread, one document at a time? Does the gap shrink with 8
> threads? With 25 documents per write?

---

## 3. Questions to answer

1. Runs A and B: did four processes cause failures, as they did in SQLite
   and DuckDB? Why not? Then compare A with C: did `WRITE_CONCERN=1` help
   through the API? Use experiment 4 and fairness rule 11 to explain.
2. Run E: how many batches succeeded, and what was the exact error? Explain
   it using the counter document and the one rule. What did run F change, and
   what did retrying cost (compare p95)?
3. Experiment 2: explain `naive`'s lost sales step by step. Then explain why
   `transaction` was correct but slow, using its retry count.
4. Experiment 3: why did the transaction in terminal 2 fail at step 5, while
   the plain update at step 7 waited? What does that tell you about when to
   use a multi-document transaction?
5. Experiment 4: what does `w: majority` wait for on a one-member replica set,
   and why do more threads help it so much? On a three-member replica set
   ([distributed track](../../../tracks/distributed/)), what else would it
   wait for?

## Going deeper

- [Concurrency and locking](../../../reference/topics/concurrency_and_locking.md):
  the same questions across all five engines.
- MongoDB docs: [Write concern](https://www.mongodb.com/docs/manual/reference/write-concern/),
  [Transactions](https://www.mongodb.com/docs/manual/core/transactions/), and
  [Atomicity](https://www.mongodb.com/docs/manual/core/write-operations-atomicity/).

## Your artifact

The filled-in tables from experiments 1, 2, and 4; what each terminal printed
in experiment 3; the **exact** text of every error you saw; and short answers
to the five questions, each citing a number from your tables.
