# 05 — Load it: MongoDB

> **Fixed question:** Get the generated `store` data in, reproducibly.
>
> **Student artifact:** One rebuild command per database, the output it
> printed, and a backup you've restored

Two loading paths, the [§4 design](../04_model/), different jobs:

| Path | Size | Source | Becomes database |
| ---- | ---- | ------ | ---------------- |
| **A. Classroom** | 1,000 purchases | the flat CSV in `datasets/store/classroom/` | `classroom` |
| **B. Generated** | 10k / 100k / 1M, `idx` and `noidx` | the **SQLite** experiment databases | `idx_10k` … `noidx_1m`, plus `writes` |

Both need the server running ([§2](../02_install/)), and `pip install pymongo`.

---

## A. Classroom build (from CSV)

```bash
python3 engines/04_mongodb/05_load/load_classroom.py
```

Expected output:

```
staging_raw documents loaded: 1000
customers        1000
products          775
purchases        1000
== verification ==
purchases 1000  revenue 28275.04  zipcodes starting with 0: 43
== rebuild complete ==
```

### The same ETL, inside the database

Read [load_classroom.py](load_classroom.py) next to
[SQLite's load_classroom.sql](../../01_sqlite/05_load/load_classroom.sql).
The plan is the same: **stage the raw file, then transform it with the
database's own query language**. Python only moves the CSV in; every
transformation is an aggregation pipeline that MongoDB runs.

| Step | SQL | MongoDB pipeline stage |
| ---- | --- | ---------------------- |
| Stage the file, every value as text | `.import` into a `TEXT` table | `insert_many` of the CSV rows as strings |
| One product per distinct name | `GROUP BY prod_name` | `$group` |
| Number them in name order | `row_number() OVER (ORDER BY ...)` | `$setWindowFields` with `$documentNumber` |
| Look up each purchase's product id | `JOIN products ON product_name = ...` | `$lookup` |
| Convert `M/D/YYYY` | a CTE that splits and zero-pads | `$dateFromString` with `format: "%m/%d/%Y"` |
| Write the result | `INSERT INTO ... SELECT` | `$merge` (insert, or replace by `_id`) |

Two things disappear. **Parents first** no longer matters, because nothing
checks references. And there's no `CREATE TABLE`: a collection appears the
first time something is written to it.

> **Predict:** the CSV's zipcodes include `01114`. The loader stages every
> value as a string. If it had let a tool guess types instead
> (`mongoimport --headerline` does), what would happen to that zipcode?
> Would anything complain?

### Rerunning it

The script drops the `classroom` database first, so every run starts from
nothing. MongoDB has no transactional "all or nothing" for a whole build
like PostgreSQL's `rebuild.sql`: if a step fails halfway, rerun the script.

---

## B. Generated builds (from the SQLite databases)

```bash
# from the repo root
python3 datasets/store/generator/make_dbs.py                  # the SQLite files, if needed
python3 engines/04_mongodb/05_load/build_mongo.py             # 10k, 100k, 1m: ~45 s
python3 engines/04_mongodb/05_load/build_mongo.py --sizes 10k # just one
python3 engines/04_mongodb/05_load/build_mongo.py --writes    # the scratch copy for §8
```

It prints one line per database: purchases, size on disk (data plus
indexes, compressed), and seconds. **Keep that output.**

### What `build_mongo.py` does

For each size, it reads `idx_<size>.db` with Python's `sqlite3`, **joins** the
tables there (so it can copy in each purchase's state, product name, and card
type), and inserts the documents in batches of 10,000. Then MongoDB builds
`monthly_sales` itself with a `$group` → `$out` pipeline, and a `counters`
document is set to the highest purchase id.

| Database | Indexes |
| -------- | ------- |
| `idx_<size>` | `_id`, the unique ones, and the same **ten** secondary indexes SQLite's `idx_*` files have, on this design's fields |
| `noidx_<size>` | `_id` and the unique ones only (email, card number, product name) |
| `writes` | a copy of `idx_100k`, for §8 to write into |

> **Connection:** the scripts use `$MONGO_URL` if it's set, otherwise
> `mongodb://localhost:27017/?directConnection=true`. If you moved the port
> (§2), `export MONGO_URL="mongodb://localhost:27018/?directConnection=true"`.

---

## C. Back it up, and prove the backup works

`mongodump` and `mongorestore` come with the MongoDB Database Tools
(`brew install mongodb-database-tools`, or use them inside the container).

```bash
mongodump    --uri "mongodb://localhost:27017/?directConnection=true" --db classroom --out backup/
mongosh      "mongodb://localhost:27017/?directConnection=true" --eval 'db.getSiblingDB("classroom").dropDatabase()'
mongorestore --uri "mongodb://localhost:27017/?directConnection=true" backup/
mongosh      "mongodb://localhost:27017/?directConnection=true" --eval 'db.getSiblingDB("classroom").purchases.countDocuments({})'
```

Look inside `backup/classroom/` before you restore. **Predict:** the data
is there, but what about the indexes and the purchase-id counter? Which
file holds each?

## Not in version control

The data lives in the Docker volume. Backup folders you create are yours;
keep them out of the repo.

## Your artifact

1. The commands you ran for A and B, and what they printed. Note the
   `idx_1m` and `noidx_1m` sizes; [§7](../07_explain/) compares them with the
   other three engines.
2. Your zipcode prediction, and how you checked it.
3. Your backup prediction, what you found in `backup/classroom/`, and the
   count after the restore.
