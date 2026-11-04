# 03 — Connect three ways: DuckDB

> **Fixed question:** The same "hello" query from the CLI, QueryMux, and Python.
>
> **Student artifact:** The hello query's output from each way you can run it

The hello query, the same as in SQLite:

```sql
SELECT count(*) AS purchases, round(sum(amount), 2) AS revenue FROM purchases;
```

Run it against `idx_10k.duckdb`, from `~/5303_data/duckdb/` or
`datasets/store/generated/duckdb/`.

## 1. The DuckDB shell

```bash
duckdb idx_10k.duckdb
```

```
D .timer on
D SELECT count(*) AS purchases, round(sum(amount), 2) AS revenue FROM purchases;
D .tables
D DESCRIBE purchases;
D .quit
```

The prompt is `D`. Dot commands work like SQLite's: `.timer on`,
`.tables`, `.mode` (try `.mode line` or `.mode markdown`). `DESCRIBE`
shows a table's columns and **types**. Compare them with SQLite's
`.schema purchases`.

Open it read-only when you only want to look:

```bash
duckdb -readonly idx_10k.duckdb
```

> **One writer process.** While a shell has the file open **for writing**, no
> other program can open it at all, not even to read. If you see
> `Could not set lock on file`, close the other shell, or open both
> read-only. [§8](../08_concurrency/) is about exactly this.

## 2. QueryMux

```bash
querymux --db idx_10k.duckdb      # detected as DuckDB from the file itself
querymux                          # or pick it from the list
```

QueryMux opens the file for each query and closes it right after. If another
program has it open for writing, the query comes back with DuckDB's
`Could not set lock on file` error instead of rows.

## 3. Python

```python
import duckdb

con = duckdb.connect("idx_10k.duckdb", read_only=True)
print(con.execute(
    "SELECT count(*) AS purchases, round(sum(amount), 2) AS revenue FROM purchases"
).fetchall())

# parameters use $name (SQLite used :name)
print(con.execute("SELECT * FROM customers WHERE customer_id = $id", {"id": 7}).fetchall())

con.close()
```

Two conveniences SQLite doesn't have:

```python
duckdb.sql("SELECT 42").show()                       # pretty-print, no connection needed
df = con.execute("SELECT * FROM products").df()      # straight into a pandas DataFrame (pip install pandas)
```

## Your artifact

The hello query's output from all three, plus one
difference you noticed between `DESCRIBE purchases` here and
`.schema purchases` in SQLite.
