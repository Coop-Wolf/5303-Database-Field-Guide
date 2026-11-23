# PostgreSQL — Concept Map Answers

PostgreSQL's column of the [concept map](../../reference/concept_map.md), with
the detail that doesn't fit in a table cell. Same questions, same order, for
every engine.

| Question                   | PostgreSQL                                                                                                                                                         |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Process model**          | Client-server. The server starts **one backend process per connection** (`max_connections`, 100 by default), so applications reuse connections through a pool.    |
| **Top-level container**    | A **cluster**: one server and its data directory, holding many databases.                                                                                         |
| **Namespace inside it**    | Database → **schema** → table. A connection uses one database; `search_path` decides which schemas an unqualified name is looked up in.                          |
| **Unit of data**           | Row, stored in a heap of 8 KB pages. An `UPDATE` writes a new row version (MVCC); VACUUM removes old ones.                                                        |
| **Who are the users?**     | **Roles.** A user is a role with `LOGIN`; a group is a role others are members of. Roles belong to the whole cluster.                                              |
| **Permission granularity** | Database (`CONNECT`), schema (`USAGE`, `CREATE`), table, column, and row (row-level security policies).                                                           |
| **Schema enforcement**     | Strict. Every value must fit its column's type; `NOT NULL`, `CHECK`, `UNIQUE`, `PRIMARY KEY`, and `FOREIGN KEY` are always enforced.                              |
| **Relationships**          | Foreign keys, always enforced, with `ON DELETE` / `ON UPDATE` `CASCADE`, `RESTRICT`, `SET NULL`. Foreign-key columns are **not** indexed automatically.           |
| **Index types**            | B-tree (default), hash, GIN (arrays, JSON, full text), GiST and SP-GiST (geometry, ranges), BRIN (huge ordered tables). Covering (`INCLUDE`), partial, and expression indexes. |
| **How to see the plan**    | `EXPLAIN` (estimates) or `EXPLAIN (ANALYZE, BUFFERS)` (runs it: actual rows, times, and pages per plan node).                                                       |
| **Transactions**           | Full ACID with MVCC. `READ COMMITTED` by default; `REPEATABLE READ` and `SERIALIZABLE` on request. Schema changes (DDL) are transactional too.                     |
| **Unit of locking**        | The **row**, for writes. Readers take no row locks. A writer waits for another writer only on the same row; deadlocks are detected and one side is cancelled.     |
| **Code inside the DB**     | Functions and procedures (SQL, PL/pgSQL, and more), triggers, and extensions written in C.                                                                         |
| **Durability knob**        | `synchronous_commit` (does COMMIT wait for the WAL on disk?), plus `fsync` and `wal_level`. `off` risks losing the last moments of commits on a crash, not corruption. |
| **Replication model**      | **Streaming** (physical: a standby replays the primary's WAL) and **logical** (publish chosen tables). Read replicas are standbys; failover is by promotion.       |
| **Sharding model**         | None built in. Partitioning splits a table across partitions on one server; the Citus extension shards across servers.                                            |
| **Backup**                 | `pg_dump` / `pg_restore` (logical, per database or schema); `pg_basebackup` plus archived WAL for point-in-time recovery.                                          |
| **CLI**                    | `psql`                                                                                                                                                             |
| **Python driver**          | `psycopg` (version 3), with `psycopg_pool` for connection pools                                                                                                   |

## Notes

- **Schemas make the experiment cheap here.** SQLite and DuckDB keep each
  experiment database in its own file. PostgreSQL keeps all of them as
  schemas in one database, and the API switches between them with
  `search_path` on a pooled connection.
- **"Strict" includes dates.** `'3/9/2026'::date` depends on the `DateStyle`
  setting; `to_date('3/9/2026', 'MM/DD/YYYY')` doesn't. Say the format when
  you load data ([§5](05_load/)).
- **Extensions are part of the answer.** Several concept-map rows (index
  types, spatial, vectors) change when you add one: PostGIS, pgvector,
  pg_trgm. The [tracks](../../tracks/) use them.
