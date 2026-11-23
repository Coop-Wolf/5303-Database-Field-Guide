# 05 — Load it: PostgreSQL

> **Fixed question:** Get the generated `store` data in, reproducibly.
>
> **Student artifact:** One rebuild command per schema, the output it printed,
> and a backup you've restored

Two loading paths, the same schema, different jobs:

| Path | Size | Source | Becomes schema |
| ---- | ---- | ------ | -------------- |
| **A. Classroom** | 1,000 purchases | the flat CSV in `datasets/store/classroom/` | `classroom` |
| **B. Generated** | 10k / 100k / 1M, `idx` and `noidx` | the **SQLite** experiment databases | `idx_10k` … `noidx_1m`, plus `writes` |

Both need the server running ([§2](../02_install/)).

---

## A. Classroom build (from CSV)

```bash
cd engines/03_postgres/05_load
psql postgresql://student:student@localhost:5432/course -f rebuild.sql
```

Expected tail of the output:

```
 purchases | revenue  | ids
-----------+----------+------
      1000 | 28275.04 | 1000
...
 == rebuild complete ==
```

### What `rebuild.sql` does

| Step | Script | What happens |
| ---- | ------ | ------------ |
| 1 | `rebuild.sql` | Drops and recreates the schema `classroom`, and points `search_path` at it |
| 2 | [../04_model/schema.sql](../04_model/schema.sql) | Tables, constraints, the `purchase_details` view |
| 3 | [load_classroom.sql](load_classroom.sql) | The ETL: stage → parents → children; moves the id counter |
| 4 | [indexes.sql](indexes.sql) | The ten secondary indexes |
| 5 | `rebuild.sql` | Row counts, a revenue round trip, then `ANALYZE` |

Steps 1 to 4 run in **one transaction**. If anything fails, even the
`DROP SCHEMA` is undone and the old `classroom` is still there. SQLite's
`rebuild.sql` doesn't do this: each of its statements commits on its own.

### Same ETL, a few new tools

Compare [load_classroom.sql](load_classroom.sql) with
[SQLite's](../../01_sqlite/05_load/load_classroom.sql). The plan is the same:
stage everything as text, fill parents first, look up ids by natural key on
the way into `purchases`. What changes:

| Step | SQLite | PostgreSQL |
| ---- | ------ | ---------- |
| Read the CSV | `.import` (a shell command) | `\copy` (a psql command): psql reads the file **on your machine** and streams it to the server |
| Staging table | a real table you drop at the end | `TEMP`: it vanishes when the session ends |
| Dates | a CTE that splits and zero-pads `M/D/YYYY` | `to_date(purchase_data, 'MM/DD/YYYY')` |
| New-id counter | none: the rowid just continues | `setval()` moves the identity counter past the loaded ids |

> **Predict:** `'3/9/2026'::date` also works on this server, with no format.
> So why does the loader spell out `'MM/DD/YYYY'`? Try
> `SET datestyle = 'ISO, DMY'; SELECT '3/9/2026'::date;` and explain.

### `\copy` or `COPY`?

`COPY purchases FROM '/path/file.csv'` also exists, and is faster, but the
path is read **by the server**, which runs inside the container and can't
see your files. `\copy` is psql doing the reading for you. The build script
in B uses `COPY ... FROM STDIN`, which is the same streaming idea from Python.

---

## B. Generated builds (from the SQLite databases)

```bash
# from the repo root
python3 datasets/store/generator/make_dbs.py                       # the SQLite files, if needed
python3 engines/03_postgres/05_load/build_postgres.py              # 10k, 100k, 1m: ~40 s
python3 engines/03_postgres/05_load/build_postgres.py --sizes 10k  # just one
python3 engines/03_postgres/05_load/build_postgres.py --writes     # the scratch copy for §8
```

It prints one line per schema: rows, size in MB, and seconds. **Keep that
output.** Your artifact uses it.

### What `build_postgres.py` does

For each size, it reads `idx_<size>.db` with Python's `sqlite3` and streams
every table into PostgreSQL with `COPY`, so all three engines hold identical
rows. Then:

| Schema | Built with |
| ------ | ---------- |
| `idx_<size>` | schema.sql + [indexes.sql](indexes.sql): the same ten secondary indexes SQLite's `idx_*` files have |
| `noidx_<size>` | schema.sql only: what `PRIMARY KEY` and `UNIQUE` create, nothing else |
| `writes` | a copy of `idx_100k`, for [§8](../08_concurrency/) to write into |

Each one also gets the `monthly_sales` rollup, the id counter moved past
the loaded rows, and **`VACUUM ANALYZE`**:

- **ANALYZE** samples each table and stores statistics (row counts, common
  values, how values are spread). The planner uses them to choose plans.
  Without them it guesses, and guesses badly.
- **VACUUM** clears out old row versions and updates the **visibility map**,
  which records which pages hold only rows every transaction can see.
  Index-only scans depend on it ([§7](../07_explain/)).

Autovacuum does both on its own eventually. Running them right after a bulk
load means your first measurements aren't taken on a table the server
doesn't understand yet.

> **Connection:** the scripts use `$DATABASE_URL` if it's set, otherwise
> `postgresql://student:student@localhost:5432/course`. If you moved the port
> (§2), `export DATABASE_URL=postgresql://student:student@localhost:5433/course`.

---

## C. Back it up, and prove the backup works

A rebuild script is one kind of reproducibility. A backup is the other: the
data exactly as it is now, including rows the API has added since.

```bash
pg_dump postgresql://student:student@localhost:5432/course --schema=classroom -f classroom.sql
psql postgresql://student:student@localhost:5432/course -c "DROP SCHEMA classroom CASCADE"
psql postgresql://student:student@localhost:5432/course -f classroom.sql
psql postgresql://student:student@localhost:5432/course -c "SELECT count(*), sum(amount) FROM classroom.purchases"
```

`pg_dump` must be the same major version as the server or newer; an older
one refuses. If yours is older, run it in the container instead:
`docker compose exec postgres pg_dump -U student course --schema=classroom > classroom.sql`.

Open `classroom.sql` in your editor before you restore it. **Predict:** does
it contain the indexes, the view, and the id counter's position, or only the
rows?

## Not in version control

The data lives in the Docker volume, not in the repo. Dump files you make
(`*.sql` outside this folder) are yours; don't commit them.

## Your artifact

1. The commands you ran for A and B, and what they printed. Note the
   `idx_1m` and `noidx_1m` sizes: [§7](../07_explain/) asks you to compare
   them with SQLite's and DuckDB's.
2. Your `DateStyle` prediction and what happened.
3. Your backup prediction, what was in the file, and the `count`/`sum` after
   the restore.
