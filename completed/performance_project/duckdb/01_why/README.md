## What DuckDB is for

I'd still choose SQLite over DuckDB for a small application that needs a lightweight database with frequent inserts, updates, and deletes. SQLite is designed for general-purpose transactional workloads (OLTP), where an application constantly reads and modifies individual rows. It stores data row by row, which makes single-record operations fast, and it handles small, frequent writes safely with full transaction support. It is also simple to deploy: the whole database lives in a single file, there is no server to install or manage, and it ships with Python's standard library, so my project needed no extra dependencies.

DuckDB, by contrast, is optimized for analytical workloads (OLAP), such as scanning, aggregating, and joining large datasets. Its columnar storage and vectorized execution make it very fast for queries that touch many rows at once, but those same design choices make it less well suited to workloads dominated by many small writes. Since my application mostly performs quick lookups and modifications on individual records, SQLite fits the workload better. If the project later grew to focus on heavy reporting or large-scale data analysis, DuckDB would become a stronger option, but for this use case SQLite is the simpler and more appropriate choice.

## Predictions

| Queries | What they do | DuckDB vs. SQLite |
| ------- | ------------ | ---------------------------------- |
| Q01, Q02 | fetch one customer; one page of products | SQlite is faster barely |
| Q03, Q04, Q05, Q06 | a date range; one customer's history; a count; streaks | Duck DB over SQLite |
| Q07–Q10 | leaderboard, anti-join, revenue by state, top products | Duck DB over SQLite |
| Q13, Q14 | whole-history reports | Duckdb over SQLite |
| Q15 | insert one purchase | SQLite over Duckdb |