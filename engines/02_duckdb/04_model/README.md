# 04 — Model the data: DuckDB

> **Fixed question:** How does the `store` dataset *want* to look in this engine?
>
> **Student artifact:** Your normalized-vs-wide comparison and the call you
> make from it (see [Part B](#part-b--your-turn-normalized-or-one-wide-table))

DuckDB is relational, so the facts you proved in
[SQLite §4](../../01_sqlite/04_model/) still hold: a zipcode determines its
state, a product name determines its price, and department belongs to the
purchase. **The eight tables don't change.** What changes is what the engine
lets you *say* about them, and what it costs to store them.

- **Part A** is a worked example: the same schema, declared the way DuckDB
  wants it, and a look at how DuckDB actually stores a column.
- **Part B** is your turn: an analytics engine raises a question SQLite
  didn't. Should the data be normalized at all?

---

## Part A — Walkthrough: the `store` schema in DuckDB

### A1. Real types

Open [schema.sql](schema.sql) next to
[SQLite's](../../01_sqlite/04_model/schema.sql). The columns are the same; the
types aren't.

| Column | SQLite | DuckDB | What the DuckDB type buys you |
| ------ | ------ | ------ | ----------------------------- |
| `purchase_date` | `TEXT` + a `GLOB` check | `DATE` | Date arithmetic, `date_trunc`, and a value that can't be malformed |
| `amount`, `unit_price` | `NUMERIC` (stored as a float) | `DECIMAL(10,2)` | Exact cents: sums don't drift |
| names, codes | `TEXT` | `VARCHAR` | Same thing; DuckDB's `VARCHAR` has no length limit |
| ids | `INTEGER` | `INTEGER` | 32-bit here; SQLite's integers are always 64-bit |

> **Predict:** SQLite accepted `'3/9/2026'` into `purchase_date` and relied on
> a `CHECK` to catch it. What does DuckDB do with the same insert?

<details>
<summary>Answer</summary>

It refuses before any constraint runs:

```
Conversion Error: invalid date field format: "3/9/2026", expected format is (YYYY-MM-DD)
```

The type *is* the check. That's why the SQLite schema's `GLOB` guard has no
counterpart in DuckDB.

</details>

### A2. Keys and constraints

| Decision | What `schema.sql` does | Why (in DuckDB) |
| -------- | ---------------------- | --------------- |
| **Primary keys, `UNIQUE`** | Declared as in SQLite | Enforced with an **ART index** (a kind of radix tree) that DuckDB builds for each one |
| **Foreign keys** | Plain `REFERENCES`, no `ON DELETE CASCADE` | **Always enforced**: there's no `PRAGMA foreign_keys`. DuckDB indexes the referencing column for you (SQLite doesn't), and doesn't support cascading actions |
| **New ids** | `DEFAULT nextval('purchase_id_seq')` | No `rowid` alias. A `SEQUENCE` hands out numbers instead |
| **Secondary indexes** | None in the schema | DuckDB doesn't need them to skip data (see A3). The `idx_*` build adds SQLite's anyway, so you can measure them in [§7](../07_explain/) |

Try the foreign key on the classroom database you build in [§5](../05_load/):

```sql
INSERT INTO purchases (customer_id, card_id, product_id, department, amount, purchase_date)
VALUES (99999, 1, 1, 'Games', 1.00, DATE '2026-01-01');
```

```
Constraint Error: Violates foreign key constraint because key "customer_id: 99999" does not exist in the referenced table
```

That's an engine fact, not a lesson you have to discover: in SQLite the same
insert succeeds unless the connection turned foreign keys on.

### A3. How a column is stored

A column store doesn't keep values the way you typed them. Each column is cut
into **row groups** of about 122,880 rows, and each piece is compressed with
whatever method suits it. Each piece also records its **min and max**, so a
scan can skip a whole row group whose range can't match the `WHERE`.

```bash
duckdb -readonly ~/5303_data/duckdb/noidx_1m.duckdb
```

```sql
SELECT column_name, any_value(compression) AS compression, count(*) AS segments
FROM pragma_storage_info('purchases')
GROUP BY ALL
ORDER BY column_name;
```

> **Predict:** `purchases` has integer ids, a 22-value `department`, a
> `DECIMAL` amount, and a `DATE`. Which columns get **dictionary** encoding
> (store each distinct value once, then small codes) and which get
> **bit-packing** (store numbers in as few bits as their range needs)?

<details>
<summary>Answer</summary>

| Column | Compression | Why |
| ------ | ----------- | --- |
| `department` | Dictionary | 22 distinct strings across a million rows. Store 22 names once, then a 5-bit code per row |
| `purchase_id`, `customer_id`, `card_id`, `product_id` | BitPacking | Integers in a known range need fewer than 32 bits each |
| `amount` | BitPacking | A `DECIMAL(10,2)` is stored as an integer number of cents |
| `purchase_date` | BitPacking | A `DATE` is stored as a day number |

Long, mostly unique strings (emails, addresses, product names) get **FSST**, a
compressor for short strings that share fragments. You'll see it in Part B.

</details>

The min/max per row group explains a puzzle you'll meet in §7: it only helps
when values are **clustered**. `purchase_id` rises row by row, so a range on it
skips nearly everything. Whether a range on `purchase_date` can skip anything
depends on how the rows were loaded. [§7](../07_explain/) asks you to find out.

### A4. Where this leaves the schema

Same eight tables, same keys, stricter types, and two things SQLite didn't
have to think about: what each constraint's index costs (§5 prints the file
sizes) and whether the normalized shape is even the right one for an
analytics engine. That's Part B.

---

## Part B — Your turn: normalized, or one wide table?

In an analytics database, a common design is **one wide table**: every
purchase with its customer, state, product, and card type already joined in.
No joins at query time. In SQLite, that design repeats every customer's name
and address on every purchase, and the file balloons.

Does that argument still hold in a column store? Test it.

### B1. Predict first

Write these down before you build anything:

1. `purchases_wide` holds every column of the `purchase_details` view, for
   1,000,000 purchases. Will its file be **smaller, about the same, or larger**
   than the whole normalized `noidx_1m.duckdb` (all eight tables)? By roughly
   how much?
2. Which will answer Q09 (revenue by state) faster: the normalized tables with
   two joins, or the wide table with none?
3. A customer moves to a new zipcode. How many rows change in each design?

### B2. Build the wide table

From any folder (outside the repo, so the file doesn't end up in iCloud or git):

```bash
duckdb wide_1m.duckdb
```

```sql
ATTACH '~/5303_data/duckdb/noidx_1m.duckdb' AS src (READ_ONLY);
CREATE TABLE purchases_wide AS SELECT * FROM src.purchase_details;
CHECKPOINT;
CALL pragma_database_size();
```

If your databases live in the repo instead, attach
`datasets/store/generated/duckdb/noidx_1m.duckdb` by its full path.
`pragma_database_size()` lists both attached databases, so you can compare
their sizes directly. Then look at how each wide column is stored:

```sql
SELECT column_name, any_value(compression) AS compression
FROM pragma_storage_info('purchases_wide')
GROUP BY ALL ORDER BY column_name;
```

### B3. Measure

Turn on `.timer on` and run each query **three times**. Use the last time.

```sql
-- normalized (Q09 as written)
SELECT z.state_code, COUNT(*) AS num_purchases, ROUND(SUM(pu.amount), 2) AS revenue
FROM src.purchases pu
JOIN src.customers c ON c.customer_id = pu.customer_id
JOIN src.zipcodes  z ON z.zipcode     = c.zipcode
GROUP BY z.state_code
ORDER BY revenue DESC, z.state_code;

-- wide
SELECT state_code, COUNT(*) AS num_purchases, ROUND(SUM(amount), 2) AS revenue
FROM purchases_wide
GROUP BY state_code
ORDER BY revenue DESC, state_code;
```

Check that both return the same 51 rows before you compare times.

### B4. Decide

Is the wide table worth it here? Answer for two different uses: the **live
store application** that records purchases, and a **nightly analytics copy**
that only answers reports.

## Your artifact

1. Your three predictions from B1, written *before* B2.

The file should be way larger.
I think the normalized tables should be faster.
Only one row will need to change since its a separate table in the no widened version.
For the widened version, every row that contains customer will need to change.


2. Both file sizes, the compression of each wide column, and both Q09 times.

noidx = 13,580 KB
wide = 25,612 KB

Q09 for first query .053 seconds
Q09 for second query .051 seconds

3. For each prediction: right or wrong, and the evidence that says why. Use the compression column to explain the file size.

   Right, Right, Right, Right

4. Your call from B4 for each of the two uses, in two or three sentences each, citing one of your numbers.

   No the wide table was not worth it here.
