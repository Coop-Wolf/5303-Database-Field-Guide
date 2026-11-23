# QueryMux

QueryMux is a split-screen terminal tool: type a query on the left, see the
rows or the error on the right. It's the "second way" to connect in every
unit's `03_connect/`, between the engine's own CLI and Python, and it keeps a
history of everything you ran.

```
QueryMux (terminal UI)  -->  local API server  -->  the database
```

## 1. Install

QueryMux is a Python tool, so install it with `pipx` (see [python.md](python.md)):

```bash
pipx install git+https://github.com/rugbyprof/QueryMUX.git
```

To update it later:

```bash
pipx upgrade querymux
```

## 2. Use it

```bash
querymux                                   # pick from the databases on this machine
querymux --list                            # the same, printed: backends ready + databases found
querymux --db store_classroom.db           # open one directly (SQLite or DuckDB, detected)
querymux --setup                           # practice databases in every engine (or press s in the picker)
```

The picker shows which engines are ready (driver installed? Postgres server
running?) and every database it found in the current folder, `$DATA_DIR`,
`$DUCKDB_DIR`, and any folders listed in `~/.querymux/config.toml`:

```toml
scan = ["~/5303_data"]
```

| Option           | Means                                                                 |
| ---------------- | --------------------------------------------------------------------- |
| `--backend`      | which engine: `sqlite`, `duckdb`, `postgres`, `postgis`, or `mongodb`. Optional for a SQLite or DuckDB file, or a `postgresql://` / `mongodb://` URL |
| `--db`           | SQLite/DuckDB: the database file. Postgres: a connection URL, e.g. `postgresql://student:student@localhost:5432/course`. MongoDB: a URL whose path is the database, e.g. `mongodb://localhost:27017/idx_10k?directConnection=true` |
| `--debug`        | verbose logging to `~/.querymux/debug.log`, with the debug pane open  |

Every query you run is logged to `~/.querymux/history.db`.

## Engines

| Engine   | Backend                | Unit                                         |
| -------- | ---------------------- | -------------------------------------------- |
| SQLite   | `sqlite`               | [01_sqlite](../engines/01_sqlite/README.md)    |
| DuckDB   | `duckdb`               | [02_duckdb](../engines/02_duckdb/README.md)    |
| Postgres | `postgres`, `postgis`  | [03_postgres](../engines/03_postgres/README.md) |
| MongoDB  | `mongodb` (type `mongosh` syntax)  | [04_mongodb](../engines/04_mongodb/README.md)  |
| Redis    | *planned*              | [05_redis](../engines/05_redis/README.md)      |

## Check

```bash
querymux --list      # sqlite ✓ and duckdb ✓; postgres ✓ once Docker is running (unit 03)
```

Then build the classroom database and open it:

```bash
cd ~/5303/5303-Database-Field-Guide/units/01_sqlite/05_load
sqlite3 store_classroom.db ".read rebuild.sql"
querymux --backend sqlite --db store_classroom.db
```

Type `SELECT count(*) FROM purchases;` and you should see `1000`.
