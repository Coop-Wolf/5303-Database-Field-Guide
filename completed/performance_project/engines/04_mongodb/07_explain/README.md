# 07 — Explain & measure: MongoDB

> **Fixed question:** What does the engine say it did, and how long did it take?
>
> **Student artifact:** `driver.py` results beside the other engines', plan
> summaries, your [§1](../01_why/) predictions checked, and answers

Same [measurement ladder](../../../lab/measurement_ladder.md): **look**,
**ask**, **time**. MongoDB's plans read differently from SQL plans, but they
answer the same question: how much did it touch to give you what you asked
for?

---

## 1. Start the API on MongoDB

[app/experiment_mongo.py](../../../lab/api/starter_code/app/experiment_mongo.py)
takes over when `ENGINE=mongodb` is set. From
[lab/api/starter_code/](../../../lab/api/starter_code/README.md) with its
`.venv` active:

```bash
pip install -e ".[dev]"                                   # picks up pymongo if you installed before it was added
ENGINE=mongodb PORT=8004 RELOAD=0 python -m app.main      # leave this running
python driver.py --base http://127.0.0.1:8004 --out results_mongodb
```

Keep `results_sqlite/`, `results_duckdb/`, and `results_postgres/` from the
earlier units beside it.

---

## 2. How MongoDB finds documents

A collection is a B-tree of documents, each stored whole (compressed) and
identified internally by a record id. Every index, `_id` included, is a
separate B-tree of **keys** pointing to record ids. That's the same shape as
SQLite and PostgreSQL. What's different is what the plan counts:

> **keys examined → documents examined → documents returned**

Every plan ends with those three numbers (the harness prints them on the
`examined:` line). The ideal is about 1 : 1 : 1: the index led straight to the
documents you wanted. Each way a plan can fall short shows up as a gap:

| Gap | Means |
| --- | ----- |
| documents examined ≫ returned | read many documents and threw most away: a missing or partial index, or a sort that needs everything first |
| keys examined ≫ documents examined | walked a lot of index for few documents: an index whose order doesn't match the filter |
| documents examined = 0 | **covered**: the index alone answered it (`PROJECTION_COVERED`, `COUNT_SCAN`) |
| keys examined = 0 | **no index used at all**: a `COLLSCAN` read every document |

**MongoDB races its candidate plans.** When more than one index could work,
the planner runs them all for a short trial, keeps the one that produced
results fastest, and caches that choice for queries of the same shape. The
losers appear in the full explain output as `rejectedPlans`
(`run_query.py ... --explain --raw`).

---

## 3. Reading the plan: the decoder

The API's `plan` field, `run_query.py --explain`, and Compass's **Explain**
button all show the same tree. Read it from the most-indented line up.

| Stage | Plain English | Grows with |
| ----- | ------------- | ---------- |
| `IDHACK` | look up one document by `_id`, skipping the planner entirely | nothing |
| `IXSCAN index {bounds}` | walk an index between those bounds | keys in range |
| `FETCH` | for each key, read its whole document (a `filter` here means "and throw away the ones that don't match") | keys passed up |
| `COLLSCAN` | read every document in the collection | **the collection** |
| `PROJECTION_COVERED` | build results from index keys alone: no `FETCH` below it | — |
| `COUNT_SCAN` | count index keys without reading any document | keys in range |
| `SORT by {...} limit N` | sort in memory (a top-N sort when a limit is given). Over 100 MB it must spill to disk or fail | documents fed in |
| `SKIP` | step past N results: they're still produced, then discarded | N |
| `LIMIT N` | stop after N | — |
| `GROUP` | `$group` pushed down into the query engine | documents fed in |
| `then $lookup`, `then $sort`, ... | pipeline stages that run after the query part, with how many documents each returned | their input |
| `examined: K keys, D documents -> returned R (T ms)` | the three numbers, and the server's own time | — |

**Red flags:** `COLLSCAN` on a big collection when you want a few documents;
documents examined ≫ returned; `SORT` fed by thousands of documents to keep
100; `SKIP` with a big number; a `$lookup` run per document over a big input.

### Three questions the plans answer

One worked example, then two for you. The index experiments use `writes`
(the 100k scratch copy): never add indexes to the experiment databases.

**1. Why read 7,296 documents to return 100?**

Q03's plan in `idx_1m`:

```
PROJECTION_DEFAULT
  SORT  by {"purchase_date": 1, "_id": 1}  limit 100
    FETCH
      IXSCAN  purchase_date_1 {"purchase_date": ["[2025-03-01, 2025-03-08)"]}
examined: 7,296 index keys, 7,296 documents -> returned 100
```

> **Predict:** the index on `purchase_date` already returns documents in
> date order. Why does MongoDB still read the whole week and sort it? What
> index would let it stop at 100?

<details>
<summary>Answer</summary>

The query sorts by `purchase_date` **and then `_id`** (the tiebreaker that
makes every engine return the same rows). `purchase_date_1` gives date order,
but within one date the `_id`s come in no particular order, so MongoDB can't
know which 100 come first without collecting every matching document and
sorting them.

An index on **both** sort keys fixes it:

```js
use writes
db.purchases.createIndex({ purchase_date: 1, _id: 1 })
```

```bash
python3 run_query.py q03.json start=2025-03-01 end=2025-03-08 --db writes --explain
```

Now there's no `SORT` stage, and it examines 100 keys and 100 documents for
100 results: the index hands them over in final order and the plan stops.
(Drop it afterwards: `db.purchases.dropIndex("purchase_date_1__id_1")`.)

The rule: **an index can replace a sort only if it contains every sort key,
in order.**

</details>

**2. Can you make Q04 read only 100 documents?** In `idx_1m`, Q04 examines
28,094 documents (every purchase of the biggest customer) to return their
100 most recent. Design an index in `writes` that brings it to about 100. Use
MongoDB's **ESR rule**: index fields for **E**quality first, then **S**ort,
then **R**ange. Report the plan before and after, and the index you chose.

**3. What did embedding buy, engine by engine?** Q09 is a three-table join
in SQL and a single `$group` here. Put its 1m time in all four engines side
by side, with each plan's main line. Which engine is fastest, and is it the
one with no join? What does each engine's plan say it read?

---

## 4. Measuring

The driver's `elapsed_ms` is the same measurement as everywhere else: from
sending the command until every document is in Python (the harness fetches
every batch inside the timer). MongoDB runs in Docker (fairness rule 8) and
pays a network round trip, as PostgreSQL did.

One fairness note specific to MongoDB: its queries run against a
**different design**. Q04 and Q09 don't join because the data was copied
in. That's the point of the unit, not a flaw in the comparison, but say so
when you report the numbers.

### Check your §1 predictions

| Queries | Your §1 prediction | PostgreSQL idx_1m (ms) | MongoDB idx_1m (ms) |
| ------- | ------------------ | ---------------------: | ------------------: |
| Q01, Q02 | | | |
| Q04 | | | |
| Q09 | | | |
| Q12 | | | |
| Q15 | | (§8) | (§8) |

### Predict before your first MongoDB driver run

| Queries | Your prediction: how much faster is `idx_*` than `noidx_*` at 1m? | What happened (cite a number) |
| ------- | ------------------------------------------------------------------ | ----------------------------- |
| Q01, Q02 | | |
| Q03–Q06 | | |
| Q07–Q10 | | |
| Q11–Q14, slow versions | | |
| Q11–Q14, `/fast` versions | | |

---

## 5. Diagnosing a slow query in MongoDB

Get the plan, look at the `examined` line, and find where keys, documents,
and results diverge. The fixes:

| Fix | In MongoDB | Examples |
| --- | ---------- | -------- |
| **Index** | Compound indexes in ESR order; covered queries (every field the query uses is in the index) | `{customer_id: 1, purchase_date: -1, _id: -1}` |
| **Reshape the document** | Copy in the field a query filters on, or embed what's read together | `state_code` on purchases made Q09 a single `$group` |
| **Rewrite** | Keyset instead of `skip`; `$sample` instead of sorting by random | Q11 fast, Q12 |
| **Precompute** | A summary collection kept by `$merge`, the way `monthly_sales` was built | Q13 fast, Q14 fast |
| **Accept it** | Some reports read everything | Q13 |

Try one more: Q08 scans all 1,000,000 purchases even in `idx_1m`, because
nothing indexes `state_code`. In `writes`, find an index that makes Q08's
plan **covered** (0 documents examined). Report the plan before and after.

## Your artifact

1. `results_mongodb/results.md` from a full driver run, beside the other
   three engines' results.
2. A plan summary for each query: the stage that explains its time, and its
   `examined` line.
3. Your §1 prediction table and the idx-vs-noidx table, completed.
4. An answer to each query's **Think about it** prompt in
   [06_queries/](../06_queries/README.md), to questions 2 and 3, and to the
   Q08 index experiment. Each answer cites a number or a plan line.
