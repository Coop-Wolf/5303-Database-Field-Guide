# DuckDB — Concept Map Answers

DuckDB's column of the [concept map](../../reference/concept_map.md), with the detail
that doesn't fit in a table cell. Same questions, same order, for every engine.

| Question                   | DuckDB                                                                                                                                                         |
| -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Process model**          | In your process. The engine is a C++ library linked into your program; there is no server. One query can use every CPU core.                                   |
| **Top-level container**    | The file. One database = one `.duckdb` file (plus `.duckdb.wal` while there are uncheckpointed writes).                                                        |
| **Namespace inside it**    | Schema → table (`main` by default). `ATTACH` adds more databases, including SQLite and PostgreSQL ones, queried as `name.schema.table`.                         |
| **Unit of data**           | Row, **stored by column**: each column is compressed separately, in row groups of 122,880 rows.                                                                |
| **Who are the users?**     | None. There are no accounts or passwords; anyone who can open the file can read it.                                                                            |
| **Permission granularity** | The file, via operating-system permissions. Read-only access = `duckdb -readonly` or `duckdb.connect(path, read_only=True)`.                                    |
| **Schema enforcement**     | Strict. A value that doesn't fit the column's type is rejected or must be cast. `NOT NULL`, `CHECK`, `PRIMARY KEY`, `UNIQUE` are enforced.                      |
| **Relationships**          | Foreign keys, **always enforced** (no setting to turn them off), and the referencing column is indexed for you. No `ON DELETE CASCADE` / `SET NULL`.           |
| **Index types**            | Zone maps: automatic min/max per row group, on every column. ART indexes for keys and `CREATE INDEX`, used only for very selective filters. Extensions add full-text (`fts`), vector (`vss`), and spatial indexes. |
| **How to see the plan**    | `EXPLAIN <query>` (estimates) or `EXPLAIN ANALYZE <query>` (actual rows and time per operator). Only `EXPLAIN ANALYZE` shows whether an index was really used.  |
| **Transactions**           | Yes, full ACID. MVCC: each transaction reads a snapshot. `BEGIN` / `COMMIT` / `ROLLBACK`.                                                                      |
| **Unit of locking**        | Between processes: **the file**. One process may open it for writing, and then no other process can open it. Within that process: rows, optimistically. A conflicting change fails at once. |
| **Code inside the DB**     | Macros (`CREATE MACRO`): reusable SQL expressions and table functions. No triggers, no stored procedures. Python functions are registered from the host (`con.create_function`). |
| **Durability knob**        | WAL plus checkpoints. `checkpoint_threshold` (16 MB by default) sets how big the WAL grows before it's folded into the file; `CHECKPOINT` forces one.            |
| **Replication model**      | None built in.                                                                                                                                                 |
| **Sharding model**         | None. One file; split data across files yourself, or query many Parquet files as one table.                                                                    |
| **Backup**                 | `EXPORT DATABASE 'dir' (FORMAT parquet)` / `IMPORT DATABASE 'dir'`, or copy the file **after** every process has closed it.                                     |
| **CLI**                    | `duckdb`                                                                                                                                                       |
| **Python driver**          | `duckdb` (`pip install duckdb`)                                                                                                                                |

## Notes

- **The file is also an interchange point.** DuckDB reads and writes CSV,
  Parquet, and JSON directly (`SELECT … FROM 'file.parquet'`, `COPY … TO`),
  and attaches SQLite and PostgreSQL databases. Many projects use it less as a
  place to *keep* data than as a tool to *query* data that lives elsewhere.
- **"No users" again.** Like SQLite, DuckDB leaves access control to the
  operating system. The same concept-map row is where PostgreSQL differs most.
- **Indexes behave differently than in a row store.** A secondary index is
  never needed to skip data: zone maps do that for every column. Whether one
  ever pays for itself is what [§7](07_explain/) asks you to measure.
