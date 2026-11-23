# 03 — Connect three ways: PostgreSQL

> **Fixed question:** The same "hello" query from the CLI, QueryMux, and Python.
>
> **Student artifact:** The hello query's output from each way you can run it

The hello query, the same as in SQLite and DuckDB:

```sql
SELECT count(*) AS purchases, round(sum(amount), 2) AS revenue FROM purchases;
```

Run it against the `idx_10k` **schema**. In PostgreSQL the six experiment
databases aren't files; they're schemas inside the `course` database
([§5](../05_load/) explains why). Every connection below uses:

```
postgresql://student:student@localhost:5432/course
           user    password  host      port database
```

## 1. psql

```bash
psql postgresql://student:student@localhost:5432/course
```

```
course=# SET search_path TO idx_10k;
course=# \timing on
course=# SELECT count(*) AS purchases, round(sum(amount), 2) AS revenue FROM purchases;
course=# \dn
course=# \dt
course=# \d purchases
course=# \q
```

The prompt is `course=#` (`=>` if you're not a superuser). Backslash
commands are psql's own, like SQLite's dot commands:

| psql | Does | SQLite / DuckDB shell |
| ---- | ---- | --------------------- |
| `\dn` | list schemas | — / `.databases` |
| `\dt` | list tables in the current `search_path` | `.tables` |
| `\d purchases` | columns, types, indexes, constraints, foreign keys | `.schema purchases` / `DESCRIBE` |
| `\timing on` | print each query's time | `.timer on` |
| `\x` | one column per line, for wide rows | `.mode line` |
| `\q` | quit | `.quit` |

**`search_path` decides which schema an unqualified name means.** Without the
`SET`, `purchases` isn't found: the default path is your user's schema, then
`public`. You can always write the full name instead: `idx_10k.purchases`.

## 2. QueryMux

```bash
querymux --backend postgres --db postgresql://student:student@localhost:5432/course
querymux                          # or pick it from the list
```

Run `SET search_path TO idx_10k;` first, or write `idx_10k.purchases`.

## 3. Python

```python
import psycopg

with psycopg.connect("postgresql://student:student@localhost:5432/course") as con:
    con.execute("SET search_path TO idx_10k")
    print(con.execute(
        "SELECT count(*) AS purchases, round(sum(amount), 2) AS revenue FROM purchases"
    ).fetchone())

    # parameters use %(name)s (SQLite used :name, DuckDB $name)
    print(con.execute("SELECT * FROM customers WHERE customer_id = %(id)s", {"id": 7}).fetchone())
```

Two things that are new compared with the file engines:

- **Values come back typed.** `revenue` is a Python `Decimal`, and dates are
  `datetime.date` objects, because the columns are `numeric` and `date`.
- **You're in a transaction until you commit.** psycopg opens one with your
  first statement; the `with` block commits when it ends. Changes made
  without a commit are invisible to everyone else, then rolled back.

## Your artifact

The hello query's output from all three, plus `\d purchases`. Point out one
thing it shows that SQLite's `.schema purchases` didn't.
