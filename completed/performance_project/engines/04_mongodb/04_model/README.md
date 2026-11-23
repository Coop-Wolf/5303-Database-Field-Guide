# 04 — Model the data: MongoDB

> **Fixed question:** How does the `store` dataset *want* to look in this engine?
>
> **Student artifact:** Your embedded-vs-referenced comparison and the call you
> make from it (see [Part B](#part-b--your-turn-what-did-embedding-buy))

In SQL, "how does the data want to look" had one answer: normalize. Store
each fact once, and join at read time. In MongoDB the question is different:
**what will be read together?** Data that's read together goes in one
document, even if that means storing a fact more than once.

The facts haven't changed. [SQLite §4](../../01_sqlite/04_model/) proved that
a zipcode determines its state and that department belongs to the purchase.
What changes is where those facts are allowed to live.

- **Part A** is a worked example: the eight `store` tables become four
  collections, one decision at a time.
- **Part B** is your turn: build the other design, the one that keeps
  references, and measure what embedding bought.

---

## Part A — Walkthrough: eight tables → four collections

Build the classroom database first ([§5](../05_load/)), then follow along in
`mongosh` with `use classroom`.

### A1. Start from the reads

Every design decision below comes from one question: *which queries does
`store` run, and what does each one need in a single read?* The
[query catalog](../../../datasets/store/query_catalog.md) answers it. Most
queries are about purchases, and many need a purchase's **state**, **product
name**, or **card type** next to it: the three things SQL joined in.

### A2. The design

```js
customers   { _id: 7, first_name, last_name, email, address, zipcode,
              state_code: "TX",                                   // from zipcodes
              cards: [ { card_id: 9, card_type: "discover", card_number } ] }   // embedded
products    { _id: 227, product_name: "Electric Pressure Cooker", unit_price: 89.99 }
purchases   { _id: 1, customer_id, card_id, product_id, department, amount, purchase_date,
              product_name, state_code, card_type }               // copied in
monthly_sales { month, state_code, department, num_purchases, revenue }
```

> **Predict:** SQL had eight tables. Four are gone: `states`, `zipcodes`,
> `card_types`, `departments`. Where did each one's information go, and why
> could MongoDB do without the table?

<details>
<summary>Answer</summary>

| SQL table | In MongoDB | Why no collection |
| --------- | ---------- | ----------------- |
| `zipcodes` | `zipcode` and `state_code` fields on each customer | Nothing reads a zipcode on its own. The fact `zipcode → state` is now stored once per customer instead of once per zipcode. |
| `states`, `card_types`, `departments` | plain string values | In SQL, these tables existed so a **foreign key** could reject a bad value. MongoDB has no foreign keys, so they would protect nothing. A validator can play that role (A4). |
| `cards` | a list **embedded** in each customer | A customer has a handful of cards, they're always read with the customer, and no query asks for a card alone. That's the textbook case for embedding: small, bounded, and owned. |

</details>

### A3. The extended reference: copying on purpose

`purchases` keeps `customer_id`, `card_id`, and `product_id`, references in
the SQL sense. It **also** stores copies of `product_name`, `state_code`, and
`card_type`. That pattern has a name: the **extended reference**. Copy into
the referencing document exactly the fields the reads need, so they never
have to follow the reference.

> **Predict:** product 227 is renamed. How many documents must change for
> every query to show the new name? Is that even what you want?

<details>
<summary>Answer</summary>

One `products` document, plus **every purchase of that product**: in the
1m data, a few hundred per product on average, all rewritten with
`updateMany`. Miss that and the copies disagree
with the product. That's the update anomaly normalization was designed to
prevent ([SQLite §4](../../01_sqlite/04_model/README.md#a2-why-the-flat-table-is-a-problem)).

But look at `amount`. SQLite already stores what the customer **was
charged**, not the current price, and calls that deliberate duplication. A
copied `product_name` can be read the same way: the name **on the receipt**.
A copied `state_code` is the state the customer lived in **when they bought**.
If those are the facts you want, the copy isn't stale; it's history. The
design is only wrong if the reads want the current value.

</details>

### A4. Types, and what MongoDB doesn't check

`amount` is `Decimal128` and `purchase_date` is a `Date`, the same exactness
SQL had with `numeric(10,2)` and `date`. (Store money as a JSON double and
every `$sum` picks up floating-point drift.) But nothing makes you use them,
and nothing checks references:

```js
db.purchases.insertOne({ _id: 999999, customer_id: 99999, card_id: 1, product_id: 1,
  department: "Garden", amount: NumberDecimal("1.00"), purchase_date: ISODate("2026-01-01") })
```

There is no customer 99999. The insert **succeeds**. In PostgreSQL, the
foreign key would have refused it.

A **validator** brings some enforcement back:

```js
db.runCommand({ collMod: "purchases", validator: { $jsonSchema: {
  bsonType: "object",
  required: ["customer_id", "card_id", "product_id", "department", "amount", "purchase_date"],
  properties: { customer_id: { bsonType: "int" }, amount: { bsonType: "decimal", minimum: 0 },
                purchase_date: { bsonType: "date" }, department: { bsonType: "string" } } } } })
```

> **Predict:** with this validator on, does an insert with
> `amount: "abc"` succeed? And the insert for customer 99999?

<details>
<summary>Answer</summary>

`amount: "abc"` fails: `Document failed validation`. Customer 99999
**still succeeds**. A validator checks each document's own shape, never
whether another document exists. References are your application's job in
MongoDB. Remove the validator afterwards (`validator: {}`) and delete
document 999999.

</details>

### A5. Where this leaves the design

| Decision | MongoDB | SQL equivalent |
| -------- | ------- | -------------- |
| Cards | embedded in the customer | `cards` table + foreign key |
| State, product name, card type on purchases | copied in (extended reference) | joins at read time |
| Lookup tables | none: plain strings, optionally a validator | tables + foreign keys |
| Purchase ids | numbers from a **counter document** (MongoDB has no auto-increment) | `INTEGER PRIMARY KEY` / identity |
| References | not enforced | enforced foreign keys |

Every catalog query except Q08 now reads **one collection with no join**.
Part B measures what that's worth.

---

## Part B — Your turn: what did embedding buy?

Build the other design, references only, the way a SQL user would naturally
model it, and run the same report both ways.

### B1. Predict first

1. Q09 (revenue by state) on the embedded design reads one collection. On a
   references-only design it needs a `$lookup` to customers for every
   purchase. How much slower will it be at 1m: about the same, 2×, 10×,
   more?
2. Will the references-only `purchases` collection take less space? By
   about how much?
3. Customer 20912 (the biggest buyer at 1m) moves to another state. How many
   documents change in each design, if every query must show the new state?

### B2. Build the references-only copy

In `mongosh` (this copies `idx_1m` into a new database, `ref_1m`):

```js
const src = db.getSiblingDB("idx_1m");
src.purchases.aggregate([
  { $project: { customer_id: 1, card_id: 1, product_id: 1, department: 1, amount: 1, purchase_date: 1 } },
  { $out: { db: "ref_1m", coll: "purchases" } } ]);
src.customers.aggregate([ { $project: { cards: 0 } }, { $out: { db: "ref_1m", coll: "customers" } } ]);
db.adminCommand({ fsync: 1 });          // flush, so the sizes below are real
```

Compare the two `purchases` collections' sizes with
`db.getSiblingDB("idx_1m").purchases.stats().storageSize` and the same for
`ref_1m`.

### B3. Measure

Run each version three times and keep the last time
(`mongosh` prints nothing about time; wrap it: `let t = Date.now(); ...; Date.now() - t`):

```js
// embedded (Q09 as written)
db.getSiblingDB("idx_1m").purchases.aggregate([
  { $group: { _id: "$state_code", num_purchases: { $sum: 1 }, revenue: { $sum: "$amount" } } },
  { $sort: { revenue: -1, _id: 1 } } ]).toArray()

// references only
db.getSiblingDB("ref_1m").purchases.aggregate([
  { $lookup: { from: "customers", localField: "customer_id", foreignField: "_id", as: "c" } },
  { $unwind: "$c" },
  { $group: { _id: "$c.state_code", num_purchases: { $sum: 1 }, revenue: { $sum: "$amount" } } },
  { $sort: { revenue: -1, _id: 1 } } ]).toArray()
```

Check both return the same 51 states and counts. Then answer B1's third
question with `countDocuments({ customer_id: 20912 })`.

When you're done: `db.getSiblingDB("ref_1m").dropDatabase()`.

### B4. Decide

For this store, which design would you ship, and what would make you switch?
Think about how often each kind of change happens: new purchases (constantly),
reports (every page view), a customer moving (rarely), a product renamed
(rarely).

## Your artifact

1. Your three predictions from B1, written before B2.
2. Both collection sizes, both Q09 times, and the B1.3 document counts.
3. For each prediction: right or wrong, and the evidence.
4. Your B4 decision in three or four sentences, citing two of your numbers,
   and one sentence on what the copied fields *mean* (current value or
   history?) in your design.
