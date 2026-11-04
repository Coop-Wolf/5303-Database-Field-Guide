# 09 — When to choose it: DuckDB

> **Fixed question:** Yes or no on the standard scenarios, citing your own numbers.
>
> **Student artifact:** Conclusions in your FINDINGS ([template](../../../lab/findings_template.md))

## The rule of thumb

> **DuckDB competes with pandas and the data warehouse, not with SQLite.**
> If the job is asking big questions of data one program owns, start with
> DuckDB. If the job is many small reads and writes from many clients, it
> isn't DuckDB's job.

## Standard scenarios

The same seven as [SQLite's §9](../../01_sqlite/09_when/), plus two that only
make sense now. For each one: **DuckDB, yes or no**, in 1–2 sentences,
citing **one number** from your own §5, §7, or §8 results. Where your SQLite
verdict differs, say which number made the difference.

| #   | Scenario                                                             | DuckDB? | The number that decides it |
| --- | -------------------------------------------------------------------- | ------- | -------------------------- |
| 1   | Internal read-only dashboard, ~10 analysts                           |         |                            |
| 2   | A mobile app's offline local storage                                 |         |                            |
| 3   | Ingesting thousands of events per second from many servers           |         |                            |
| 4   | A fresh throwaway database for each automated test                   |         |                            |
| 5   | A web API with many users who write                                  |         |                            |
| 6   | A desktop app's document format                                      |         |                            |
| 7   | Several applications sharing one database with different permissions |         |                            |
| 8   | A nightly report over a copy of the production database              |         |                            |
| 9   | Exploring a folder of Parquet files in a notebook                    |         |                            |

Decide first, then go find the number. If the number argues against your
verdict, change the verdict.

## The "both" answer

Many real systems use **two** databases: one for the application's live data
(SQLite or Postgres), and DuckDB for analytics over a copy of it. Your §5
build script is a small version of that: it reads SQLite and writes DuckDB.

Pick one scenario above where "both" is a better answer than either engine
alone. Say which engine does which job, and what moves data between them.

## Sweet spots and red flags

| DuckDB fits when…                                              | Look elsewhere when…                                                         |
| -------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| queries scan, join, and aggregate many rows                    | the work is mostly single-row lookups and small writes                       |
| one program owns the data (a notebook, a script, a report job) | several processes need to write, or to read while one writes                 |
| data arrives in batches, or already sits in CSV / Parquet      | writes trickle in one row at a time, all day                                 |
| you want zero operations: no server, one file                  | you need users, roles, and permissions ([Postgres](../../03_postgres/))      |
| the machine has cores and memory to spare                      | the footprint must be tiny ([SQLite](../../01_sqlite/))                      |

## Your artifact

The nine verdicts above in your FINDINGS, each with one sentence and one
number from your own results, plus your "both" scenario.
