# 02 — Install & verify: DuckDB

> **Fixed question:** Can I run it and prove it's running?
>
> **Student artifact:** Output of the verify commands below

DuckDB is two separate installs, the same as SQLite: a **command-line
shell** for typing queries, and a **Python package** for programs. Neither
needs a server.

## 1. The command-line shell

| OS      | Install                                                                        |
| ------- | ------------------------------------------------------------------------------ |
| macOS   | `brew install duckdb`                                                          |
| Windows | `winget install DuckDB.cli`                                                    |
| Linux   | download the `duckdb_cli` zip for your platform from [duckdb.org](https://duckdb.org/docs/installation/), unzip, put `duckdb` on your `PATH` |

## 2. The Python package

Inside your project's venv (see [setup/python.md](../../../setup/python.md)):

```bash
pip install duckdb
```

The [measurement API](../../../lab/api/starter_code/README.md) installs it
for you as a dependency.

## 3. Extensions

DuckDB keeps optional features in **extensions** it downloads the first time
you use them: `sqlite` (read SQLite files), `parquet` and `json` (built in),
`fts` (full-text search), and others. This unit uses `sqlite`, which
installs itself when the build script runs `INSTALL sqlite; LOAD sqlite;`.
That needs an internet connection once.

## Verify

```bash
duckdb --version
duckdb -c "SELECT 42 AS answer, version() AS duckdb_version"
python3 -c "import duckdb; print(duckdb.sql('SELECT 42 AS answer').fetchall(), duckdb.__version__)"
```

All three should answer. If the CLI and the Python package report different
versions, that's fine for this course: the file format has been stable since
1.0.

## Then build the experiment databases

The DuckDB databases are built **from the SQLite ones**, so both engines hold
exactly the same rows. From the repo root:

```bash
python3 datasets/store/generator/make_dbs.py        # if you haven't already
python3 engines/02_duckdb/05_load/build_duckdb.py
```

[§5](../05_load/) explains what that script does.
