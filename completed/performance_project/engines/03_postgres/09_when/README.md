# 09 — When to choose it: PostgreSQL

> **Fixed question:** Yes or no on the standard scenarios, citing your own numbers.
>
> **Student artifact:** Conclusions in your FINDINGS ([template](../../../lab/findings_template.md))

## The rule of thumb

> **When more than one program, person, or machine shares the data, start
> with PostgreSQL.** Move away from it when you can name the reason:
> one program owns the data (SQLite), the job is big scans (DuckDB), or
> the data isn't rows at all (the next two units).

## Standard scenarios

The same seven as [SQLite](../../01_sqlite/09_when/) and
[DuckDB](../../02_duckdb/09_when/), plus two that only a server makes
possible. For each: **PostgreSQL, yes or no**, in 1–2 sentences, citing
**one number** from your own §5, §7, or §8 results. Where your verdict
differs from SQLite's or DuckDB's, say which number made the difference.

| #   | Scenario                                                             | PostgreSQL? | The number that decides it |
| --- | -------------------------------------------------------------------- | ----------- | -------------------------- |
| 1   | Internal read-only dashboard, ~10 analysts                           |             |                            |
| 2   | A mobile app's offline local storage                                 |             |                            |
| 3   | Ingesting thousands of events per second from many servers           |             |                            |
| 4   | A fresh throwaway database for each automated test                   |             |                            |
| 5   | A web API with many users who write                                  |             |                            |
| 6   | A desktop app's document format                                      |             |                            |
| 7   | Several applications sharing one database with different permissions |             |                            |
| 8   | An online store selling limited stock to many buyers at once         |             |                            |
| 9   | A nightly report over a year of purchases                            |             |                            |

Decide first, then go find the number. If the number argues against your
verdict, change the verdict.

## Three engines, one table

You've now measured three engines on the same rows. Fill this in from your
own results; it becomes the core of your FINDINGS:

| Job | SQLite | DuckDB | PostgreSQL | Your pick, and the number |
| --- | ------ | ------ | ---------- | ------------------------- |
| One row by key (Q01) | | | | |
| A whole-table report (Q09 or Q13) | | | | |
| Many writers from 4 processes (§8, run B) | | | | |
| Who can read what (§4) | | | | |

## Sweet spots and red flags

| PostgreSQL fits when…                                           | Look elsewhere when…                                                        |
| --------------------------------------------------------------- | --------------------------------------------------------------------------- |
| many clients read and write the same data at once               | the data belongs to one program on one device ([SQLite](../../01_sqlite/)) |
| correctness matters: constraints, transactions, isolation       | the work is big scans and aggregates over many rows ([DuckDB](../../02_duckdb/)) |
| different users need different permissions                      | the data is documents of varying shape ([MongoDB](../../04_mongodb/))       |
| you want one database that also does maps, text search, vectors | you need sub-millisecond lookups of hot keys at huge rates ([Redis](../../05_redis/)) |
| you can run (or rent) a server                                  | nobody will operate a server, and SQLite would do                           |

## Your artifact

The nine verdicts in your FINDINGS, each with one sentence and one number
from your own results, plus the completed three-engine table.
