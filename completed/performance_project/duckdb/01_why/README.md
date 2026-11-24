## What DuckDB is for

I'd still choose SQLite over DuckDB for a small application that needs a lightweight database with frequent inserts, updates, and deletes. DuckDB is optimized for analytical workloads, such as querying large datasets, whereas SQLite is designed for general-purpose transactional workloads.

## Predictions

| Queries | What they do | DuckDB vs. SQLite: your prediction |
| ------- | ------------ | ---------------------------------- |
| Q01, Q02 | fetch one customer; one page of products | SQlite is faster barely |
| Q03, Q04, Q05, Q06 | a date range; one customer's history; a count; streaks | Duck DB |
| Q07–Q10 | leaderboard, anti-join, revenue by state, top products | Duck DB |
| Q13, Q14 | whole-history reports | Duckdb |
| Q15 | insert one purchase | SQLite |
