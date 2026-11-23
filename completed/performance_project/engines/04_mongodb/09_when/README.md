# 09 — When to choose it: MongoDB

> **Fixed question:** Yes or no on the standard scenarios, citing your own numbers.
>
> **Student artifact:** Conclusions in your FINDINGS ([template](../../../lab/findings_template.md))

## The rule of thumb

> **Choose MongoDB when the data is naturally a document: read and written
> as one piece, varying in shape, and rarely joined.** If the questions you
> ask keep crossing between kinds of things (customers *and* products *and*
> states), the relational engines are built for that and MongoDB isn't.

## Standard scenarios

The same seven as the other units, plus two that a document store makes
interesting. For each: **MongoDB, yes or no**, in 1–2 sentences, citing
**one number** from your own §4, §7, or §8 results. Where your verdict
differs from PostgreSQL's, say which number made the difference.

| #   | Scenario                                                             | MongoDB? | The number that decides it |
| --- | -------------------------------------------------------------------- | -------- | -------------------------- |
| 1   | Internal read-only dashboard, ~10 analysts                           |          |                            |
| 2   | A mobile app's offline local storage                                 |          |                            |
| 3   | Ingesting thousands of events per second from many servers           |          |                            |
| 4   | A fresh throwaway database for each automated test                   |          |                            |
| 5   | A web API with many users who write                                  |          |                            |
| 6   | A desktop app's document format                                      |          |                            |
| 7   | Several applications sharing one database with different permissions |          |                            |
| 8   | A product catalog where every category has different attributes      |          |                            |
| 9   | Moving money between two accounts                                    |          |                            |

Decide first, then go find the number. If the number argues against your
verdict, change the verdict.

## Four engines, one table

| Job | SQLite | DuckDB | PostgreSQL | MongoDB | Your pick, and the number |
| --- | ------ | ------ | ---------- | ------- | ------------------------- |
| One record by key (Q01) | | | | | |
| A report across the data (Q09) | | | | | |
| 10 random records (Q12) | | | | | |
| Many writers from 4 processes (§8 run B) | | | | | |
| One hot row/document, 8 clients (§8 experiment 2, best correct strategy) | | | | | |
| Keeping copies correct (§4) | | | | | |

## Sweet spots and red flags

| MongoDB fits when…                                            | Look elsewhere when…                                                      |
| ------------------------------------------------------------- | ------------------------------------------------------------------------- |
| each record is read and written as one unit                   | most questions join several kinds of things ([PostgreSQL](../../03_postgres/)) |
| records vary in shape, or the shape changes often             | the database must enforce references and constraints for you             |
| data nests naturally: orders with lines, posts with comments  | many transactions touch several records at once                         |
| you want replication and failover built in                    | the job is big analytical scans ([DuckDB](../../02_duckdb/))             |
| the team thinks in JSON objects                               | the data is one program's local file ([SQLite](../../01_sqlite/))        |

## Your artifact

The nine verdicts in your FINDINGS, each with one sentence and one number
from your own results, plus the completed four-engine table.
