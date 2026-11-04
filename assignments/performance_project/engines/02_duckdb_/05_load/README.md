# 05 — Load it: DuckDB

> **Fixed question:** Get the generated `store` data in, reproducibly.
>
> **Student artifact:** One rebuild command per database, the output it
> printed, and your Parquet comparison

DuckDB reads other people's files for a living, so there are three loading
paths. They produce the **same schema** for different jobs:

| Path | Size | Source | Use |
| ---- | ---- | ------ | --- |
| **A. Classroom** | 1,000 purchases | the flat CSV in `datasets/store/classroom/` | Live demos, QueryMux, the ETL steps |
| **B. Generated** | 10k / 100k / 1M, `idx` and `noidx` | the **SQLite** experiment databases | [§7](../07_explain/) and [§8](../08_concurrency/): same rows as SQLite, so the engines compare fairly |
| **C. Parquet** | any | files you export | The format analytics tools trade in. Query it without loading it |

---

## A. Classroom build (from CSV)

```bash
cd engines/02_duckdb/05_load
rm -f store_classroom.duckdb
duckdb store_classroom.duckdb ".read rebuild.sql"
```

Expected tail of the output:

```
│ == verification == │
...
│      1000 │      28275.04 │     1000 │    28275.04 │
...
│ == rebuild complete == │
```

### What `rebuild.sql` does

| Step | Script | What happens |
| ---- | ------ | ------------ |
| 1 | [../04_model/schema.sql](../04_model/schema.sql) | Drops and recreates every table, the sequence, and the `purchase_details` view. Safe to re-run. |
| 2 | [load_classroom.sql](load_classroom.sql) | The ETL: stage → parents → children, then moves the id sequence past the loaded rows. |
| 3 | `rebuild.sql` itself | Round-trips the row count and revenue against the CSV. |

There's no foreign-key check step. DuckDB checks foreign keys on every insert,
so a load that finished can't have broken one.

### Same ETL, fewer steps

Compare [load_classroom.sql](load_classroom.sql) with
[SQLite's](../../01_sqlite/05_load/load_classroom.sql). The plan is the same:
stage the raw file, fill parents first, look up ids by natural key on the way
into `purchases`. Two steps disappear:

| SQLite | DuckDB |
| ------ | ------ |
| `CREATE TABLE staging_raw (... TEXT ...)`, then `.import` | `CREATE TABLE staging_raw AS SELECT * FROM read_csv('...')`: one statement |
| A CTE that splits `M/D/YYYY` and zero-pads it to ISO text | Nothing: the CSV reader recognizes the date format and returns a `DATE` |

`read_csv` **sniffs** the file: it samples the rows and guesses each column's
type. SQLite's §4 warned that letting a tool guess types turns zipcode `01114`
into the number `1114`.

> **Predict, then check:** what type will the sniffer give `zipcode`, and
> `purchase_amount`? Run this from `05_load/`:
>
> ```bash
> duckdb -c "DESCRIBE SELECT * FROM read_csv('../../../datasets/store/classroom/store_flat.csv')"
> ```
>
> Was trusting the sniffer safe *for this file*? Is it safe in general? The
> loader inserts `purchase_amount` into a `DECIMAL(10,2)` column. Does that
> matter?

> **Classroom-size caveat:** the CSV has exactly **one purchase per
> customer**, so per-customer queries (Q04, Q06) return almost nothing. Use
> the generated data for those.

---

## B. Generated builds (from the SQLite databases)

The DuckDB experiment databases are **copied from the SQLite ones**, so both
engines hold identical rows. Build the SQLite files first if you haven't:

```bash
# from the repo root
python3 datasets/store/generator/make_dbs.py
python3 engines/02_duckdb/05_load/build_duckdb.py              # 10k, 100k, 1m
python3 engines/02_duckdb/05_load/build_duckdb.py --sizes 10k  # just one, for a quick test
```

It prints one line per file: rows, size in MB, and seconds. **Keep that
output.** Your artifact uses it.

### What `build_duckdb.py` does

For each size it attaches `idx_<size>.db` through DuckDB's `sqlite`
extension, reads every table, and writes two files:

| File | Built with | Constraints and indexes |
| ---- | ---------- | ----------------------- |
| `idx_<size>.duckdb` | [schema.sql](../04_model/schema.sql), then `INSERT … SELECT` from SQLite | Primary keys, `UNIQUE`, foreign keys, **plus SQLite's ten secondary indexes** |
| `noidx_<size>.duckdb` | `CREATE TABLE … AS SELECT` from SQLite | None: same columns, same types, same rows |

Both get the `monthly_sales` summary table (the `/fast` versions of Q13 and Q14
read it) and the `purchase_details` view. On the way in, the script casts
SQLite's ISO-text dates to `DATE` and its floating-point amounts to
`DECIMAL(10,2)`.

**Where the files go:** `$DUCKDB_DIR` if set; otherwise a `duckdb/` folder
next to the SQLite files, so `~/5303_data/duckdb/` if your `DATA_DIR` is
`~/5303_data/sqlite/`, or `datasets/store/generated/duckdb/` by default.

> **If the build fails with `Could not set lock on file`,** something else has
> that `.duckdb` file open for writing: a shell, QueryMux, or the measurement
> API. Close it and run the build again.

---

## C. Parquet: data that's already "loaded"

[Parquet](https://parquet.apache.org/) is a column-oriented **file format**:
columns, types, compression, and per-block min/max, in a file any analytics
tool can read (pandas, Polars, Spark, BigQuery, DuckDB). DuckDB queries it in
place, with no load step.

Export the 1M purchases two ways, from a scratch folder **outside the repo**
(the files are large; `*.parquet` is git-ignored anyway):

```bash
duckdb -readonly ~/5303_data/duckdb/noidx_1m.duckdb \
  "COPY purchases TO 'purchases_1m.parquet' (FORMAT parquet);
   COPY purchases TO 'purchases_1m.csv';"
ls -lh purchases_1m.*
```

Then query each file directly:

```bash
duckdb -c ".timer on" \
  -c "SELECT count(*), sum(amount) FROM 'purchases_1m.parquet'" \
  -c "SELECT count(*), sum(amount) FROM 'purchases_1m.csv'" \
  -c "DESCRIBE SELECT * FROM 'purchases_1m.parquet'" \
  -c "DESCRIBE SELECT * FROM 'purchases_1m.csv'"
```

> **Predict before you run it:** which file is smaller? Which query is
> faster? Will both return the *same* `sum(amount)`?

And the whole database in one command, which is also DuckDB's backup format:

```bash
duckdb -readonly ~/5303_data/duckdb/noidx_10k.duckdb "EXPORT DATABASE 'export_10k' (FORMAT parquet)"
ls export_10k     # one .parquet per table, plus schema.sql and load.sql
```

`IMPORT DATABASE 'export_10k'` in an empty database rebuilds it.

---

## Not in version control

`*.duckdb`, `*.duckdb.wal`, and `*.parquet` are build artifacts, covered by the
repo `.gitignore`. Rebuild them from the scripts; never commit them.

## Your artifact

1. The command you used for each build (classroom and generated), and what it
   printed. Note the `idx_1m` and `noidx_1m` sizes: [§7](../07_explain/) asks
   you to explain them.
2. Your sniffer prediction and what `DESCRIBE` showed.
3. From part C: both file sizes, both query times, both sums, and your
   prediction next to each. Then one or two sentences: **what did the CSV
   lose that the Parquet file kept, and how do you know?**
