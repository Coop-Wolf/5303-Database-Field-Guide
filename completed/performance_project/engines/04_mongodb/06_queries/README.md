# 06 — Run the query catalog: MongoDB

> **Fixed question:** Translate Q01–Q15, or say why one can't or shouldn't be translated.
>
> **Student artifact:** All 19 routes answering with `ENGINE=mongodb`, and the
> translation table below filled in

Files: `qNN.json` per query, `qNN_fast.json` for rewrites. Routes follow the
[route contract](../../../lab/api/02_route_contract/).

There's no SQL to port this time. Each file is the **command** MongoDB
receives, written as JSON: a `find`, an `aggregate` with its pipeline, or,
for Q15, a short recipe of commands. Every query returns the same rows as
SQLite's version. The comments live under the `"//"` key (JSON has no
comments), including each query's **Think about it** prompt for [§7](../07_explain/).

## How to read one

```json
{
  "//": ["Q04 — One customer's purchase history", "..."],
  "find": "purchases",
  "filter": { "customer_id": "{{customer_id}}" },
  "projection": { "_id": 0, "purchase_id": "$_id", "purchase_date": 1, "product_name": 1, ... },
  "sort": { "purchase_date": -1, "_id": -1 },
  "limit": 100
}
```

- `{{customer_id}}` is a **placeholder**: the API fills it with the route's
  parameter. `{{start:date}}` becomes a real date, `{{start:month}}` the text
  `'2025-03'`, `{{amount:decimal}}` an exact decimal.
- `"$_id"` with a `$` means *the value of the field `_id`*; plain `1` means
  *include this field*. So the projection renames `_id` to `purchase_id`.

## The catalog in MongoDB

| ID | Query | Fit | Command | File(s) |
| -- | ----- | :-: | ------- | ------- |
| Q01 | One customer by id | ✓ | `find` | [q01.json](q01.json) |
| Q02 | One page of products | ✓ | `find` + `skip` | [q02.json](q02.json) |
| Q03 | Purchases in a date range | ✓ | `find` | [q03.json](q03.json) |
| Q04 | A customer's purchase history | ✓ | `find`: no join, `product_name` is copied in | [q04.json](q04.json) |
| Q05 | Count purchases in one department | ✓ | `aggregate`: `$match`, `$count` | [q05.json](q05.json) |
| Q06 | A customer's purchase streaks | ~ | `aggregate` with `$setWindowFields` | [q06.json](q06.json) |
| Q07 | 90-day spending leaderboard | ~ | `aggregate` with `$rank` | [q07.json](q07.json) |
| Q08 | Products never bought in a state | ~ | `aggregate`: collect the bought ids, `$lookup` the rest | [q08.json](q08.json) |
| Q09 | Revenue by state | ✓ | `aggregate`: no join, `state_code` is copied in | [q09.json](q09.json) |
| Q10 | Top 10 products by revenue | ✓ | `aggregate` | [q10.json](q10.json) |
| Q11 | Deep pagination: skip vs keyset | ✓ | `find` | [q11.json](q11.json) · [q11_fast.json](q11_fast.json) |
| Q12 | Random sample | ✓ | `$sample` | [q12.json](q12.json) · [q12_fast.json](q12_fast.json) |
| Q13 | Revenue by month: scan vs summary | ✓ | `aggregate` | [q13.json](q13.json) · [q13_fast.json](q13_fast.json) |
| Q14 | State × department × month report | ~ | `aggregate`: one `$group` on three keys | [q14.json](q14.json) · [q14_fast.json](q14_fast.json) |
| Q15 | Insert a purchase | ~ | three commands: counter, copy-in, `insert` | [q15.json](q15.json) · [q15_fast.json](q15_fast.json) |

**~** means it works but isn't how MongoDB is happiest: more verbose than the
SQL, or more steps. The [patterns](../../../reference/patterns/) pages say why
for each.

## Translate SQL to pipeline stages

Put a catalog query's SQL next to its JSON and match the pieces. Fill in the
middle column; the first row is done:

| SQL | MongoDB | Seen in |
| --- | ------- | ------- |
| `WHERE` | `$match` (in a pipeline) or `filter` (in a `find`) | Q03, Q05, Q14 |
| `GROUP BY ... count(*), sum(...)` | | Q09, Q13 |
| `ORDER BY` | | |
| `LIMIT` / `OFFSET` | | Q02, Q11 |
| `SELECT a, b AS c` | | |
| `HAVING` | | Q14 |
| `ROW_NUMBER()` / `RANK()` | | Q06, Q07 |
| `JOIN` | | Q08 |

Then answer:

1. **Which catalog queries got simpler** than their SQL because of the §4
   design, and why? Which got **harder**?
2. Q15 is three commands where SQL needed one `INSERT`. Name what each
   command does, and which of SQL's features it replaces.

### Shortcuts the catalog doesn't use

| Query | MongoDB shortcut | Docs |
| ----- | ---------------- | ---- |
| Q09 | `{ $sortByCount: "$state_code" }`: group, count, and sort in one stage | [$sortByCount](https://www.mongodb.com/docs/manual/reference/operator/aggregation/sortByCount/) |
| Q10 | `$topN` inside `$group`: the top products without a separate `$sort` | [$topN](https://www.mongodb.com/docs/manual/reference/operator/aggregation/topN/) |
| Q13 | `$dateTrunc` instead of `$dateToString` | [$dateTrunc](https://www.mongodb.com/docs/manual/reference/operator/aggregation/dateTrunc/) |
| Q14 | `$facet`: several groupings over one scan | [$facet](https://www.mongodb.com/docs/manual/reference/operator/aggregation/facet/) |

## Running a query by hand

[run_query.py](run_query.py) fills in the placeholders and runs the command
(it needs the API's packages: run it with the lab's `.venv` active):

```bash
cd engines/04_mongodb/06_queries
python3 run_query.py q01.json customer_id=7                                # database classroom
python3 run_query.py q03.json start=2025-03-01 end=2025-03-08 --db idx_1m
python3 run_query.py q04.json customer_id=20912 --db idx_1m --explain
python3 run_query.py q04.json customer_id=20912 --show-command             # paste into mongosh
```

`--show-command` prints the filled-in command as `db.runCommand({...})`,
with real `ISODate(...)` and `NumberDecimal(...)` values, ready to paste into
`mongosh` or Compass.

## In the API

The routes don't change; the harness does. Start the API with
`ENGINE=mongodb` ([§7](../07_explain/#1-start-the-api-on-mongodb)). Your Q03,
Q08, and Q15 routes from the SQLite unit work as they are: they call
`run_query` and `run_write`, and the MongoDB harness does the rest.

## Your artifact

1. The translation table, completed, and your answers to questions 1 and 2.
2. Every route answering in `/docs` with `ENGINE=mongodb` against `idx_10k`,
   and every `/fast` route returning the same rows as its slow twin (Q12 is
   random, so it's the exception).
3. One shortcut you tried: the pipeline, proof it returns the same rows, and
   one sentence on whether its plan differs.
