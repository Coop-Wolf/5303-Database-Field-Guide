# 01 — Why it exists: PostgreSQL

> **Fixed question:** What problem was this built for, and what does it give up?
>
> **Student artifact:** One paragraph, plus your predictions (below)

## The problem PostgreSQL solves

SQLite and DuckDB answer one program's questions about its own data. Most
real systems aren't like that. A store has a website, a phone app, a
warehouse scanner, an accounting job, and three analysts, all reading and
writing the same purchases **at the same time, from different machines**.
That needs things a file can't give you:

| Need | What a file engine does | What a server does |
| ---- | ----------------------- | ------------------ |
| Many programs writing at once | one writer at a time, for the whole file | many writers; they only wait for each other on the **same row** |
| Clients on other machines | they can't reach the file | they connect over the network |
| Different people, different permissions | whoever can read the file reads everything | logins, roles, `GRANT` per schema, table, even column |
| Guarantees under load | yours to arrange | ACID transactions, enforced constraints, crash recovery |

PostgreSQL started as the POSTGRES research project at UC Berkeley in 1986
and became an open-source SQL database in 1996. Today it's the default answer
to "which database should a new application use?" It's strict about types
and constraints, has one of the most capable SQL dialects, and an extension
system (PostGIS for maps, pgvector for embeddings) that turns it into much
more than a relational engine.

## The mental model: a server that owns the data

```
 your program          another program       psql
      │                       │                │
      └──── network connection (port 5432) ────┘
                         │
          ┌──────────────▼──────────────────────────────┐
          │ PostgreSQL server                           │
          │   one backend process per connection        │
          │   shared buffers (pages cached in memory)   │
          │   WAL writer, autovacuum, checkpointer, ... │
          └──────────────┬──────────────────────────────┘
                         ▼
          data directory: tables, indexes, WAL  (only the server touches it)
```

From your program's side, the difference from SQLite is one line: you
**connect** instead of opening a file. Everything else follows from that
connection:

- Every query is a **round trip**: send the SQL, wait for the server, receive
  rows. Even a query that does no work pays it.
- Every connection costs the server a **process** and some memory, so
  applications keep a small **pool** of open connections and reuse them.
- The server can see **all** the clients, so it can coordinate them: it knows
  who holds which row, and who's waiting.

## How many writers at once? MVCC

A row store with many writers has a problem SQLite avoids by allowing only
one: what does a reader see while someone else is halfway through changing
a row?

PostgreSQL's answer is **MVCC** (multi-version concurrency control). An
`UPDATE` doesn't overwrite a row; it writes a **new version** and marks the
old one as ended. Each transaction sees the versions that were committed when
it started. So:

- **Readers never wait for writers, and writers never wait for readers.**
- **Two writers wait for each other only on the same row.** One customer's
  purchase and another customer's purchase never collide.
- **Old versions pile up**, and a background job, **VACUUM**, cleans them
  away later. That's a cost SQLite doesn't have.

## What it gives up

| Trade-off | Consequence |
| --------- | ----------- |
| **It's a server** | Something has to run it, patch it, back it up, and watch it. That's Docker for you; it's a job for a company. |
| **Every query is a round trip** | Send, wait, receive, even when the work itself is trivial. A library engine never pays that. |
| **Connections are expensive** | Thousands of clients need a connection pool (or a pooler like PgBouncer) in front. |
| **MVCC leaves old row versions behind** | VACUUM has to clean up, and tables can bloat if it falls behind. |
| **Rows, not columns** | A report that totals one column still reads every whole row, the same as SQLite. Several CPU cores can share the work. |
| **More to configure** | Users, passwords, ports, `pg_hba.conf`, memory settings: more power, more ways to get it wrong. |

## Your artifact

1. Write one paragraph: *what PostgreSQL is for that SQLite isn't, and one
   job where you'd still choose SQLite.*
2. **Predict, before you measure anything.** For each group, will
   PostgreSQL (indexed, at 1m) be faster, slower, or about the same as
   SQLite? Keep this; [§7](../07_explain/) and [§8](../08_concurrency/)
   check it.

| Queries | What they do | PostgreSQL vs. SQLite: your prediction |
| ------- | ------------ | -------------------------------------- |
| Q01, Q02 | fetch one customer; one page of products | |
| Q03–Q06 | a date range; one customer's history; a count; streaks | |
| Q08 | products never bought in a state (try noidx too) | |
| Q09, Q10, Q13 | whole-table reports | |
| Q15 with 4 API worker processes | insert purchases | |

Then read PostgreSQL's column of the [concept map](../../../reference/concept_map.md)
and [concept_answers.md](../concept_answers.md).
