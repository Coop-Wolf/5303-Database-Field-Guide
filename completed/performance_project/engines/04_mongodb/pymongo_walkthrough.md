# PyMongo walkthrough: from `find_one` to aggregation pipelines

> **What this is:** a hands-on handout that builds MongoDB queries up from
> Python, one new idea at a time, against the `idx_10k` database. Every
> output shown here was produced by running the code.
>
> **Before you start:** the server is running ([§2](02_install/)), `idx_10k`
> is loaded ([§5](05_load/)), and you're in a venv with `pymongo` installed
> (the lab API's `.venv` has it).

The walkthrough follows a run of business questions, each needing one more
query feature than the last:

**find a customer → filter purchases → sort and page → summarize → group by
anything → connect collections → ask whether it's fast**

Parts 1–3 are `find()`. Parts 4–9 are the **aggregation pipeline**, which is
where most of the real work happens, and they get most of the space.

| Part                                       | Question                                 | New ideas                                                           |
| ------------------------------------------ | ---------------------------------------- | ------------------------------------------------------------------- |
| [1](#part-1--retrieve-documents)           | Who is customer 7?                       | `find_one`, `find`, cursors, projections                            |
| [2](#part-2--filter)                       | Which purchases match?                   | comparison operators, AND / OR / `$in`, dates, arrays, `$elemMatch` |
| [3](#part-3--sort-limit-page-count)        | What's on top?                           | `sort`, tie-breakers, `skip` vs keyset, counting                    |
| [4](#part-4--the-aggregation-pipeline)     | How does a pipeline think?               | stages, document shape, SQL ↔ stage map                             |
| [5](#part-5--group)                        | How much, per what?                      | `$group`, accumulators, `$sort` after `$group`, `$project`          |
| [6](#part-6--group-by-anything)            | Per state *and* department? Per month?   | compound keys, computed keys, `$bucket`, HAVING                     |
| [7](#part-7--sorting-inside-a-pipeline)    | The best department in each state?       | sort-then-group, `$first`, `$topN`, grouping twice                  |
| [8](#part-8--arrays-and-other-collections) | Cards held? Customer names?              | `$unwind`, `$lookup`                                                |
| [9](#part-9--beyond-group)                 | Running totals? Several reports at once? | `$setWindowFields`, `$facet`                                        |
| [10](#part-10--is-it-fast)                 | Will it scale?                           | `explain()`, index use, stage order                                 |

---

## Setup

```python
from datetime import datetime
from pprint import pprint

from bson.decimal128 import Decimal128
from pymongo import ASCENDING, DESCENDING, MongoClient

client = MongoClient("mongodb://localhost:27017/?directConnection=true")
db = client["idx_10k"]

print(db.list_collection_names())
```

```text
['purchases', 'monthly_sales', 'counters', 'products', 'customers']
```

The shape of the data ([§4](04_model/) explains why it looks like this):

```python
customers  {_id, first_name, last_name, email, address, zipcode, state_code,
            cards: [{card_id, card_type, card_number}, ...]}         # 500 docs
products   {_id, product_name, unit_price}                            # 100 docs
purchases  {_id, customer_id, card_id, product_id, department, amount,
            purchase_date, product_name, state_code, card_type}       # 10,000 docs
```

Two things to keep in mind throughout:

- **Each purchase is one product.** There are no line items. The only array
  in the data is a customer's `cards`.
- **Money is `Decimal128`** and **dates are real `datetime`s**. You'll see
  `Decimal128('264.04')` in output. To do Python arithmetic on one, call
  `.to_decimal()` first. MongoDB itself compares and sums them exactly.

---

## Part 1 — Retrieve documents

### 1.1 `find_one()` returns a document or `None`

"Who is customer 7?"

```python
customer = db.customers.find_one({"_id": 7})
pprint(customer)
```

```text
{'_id': 7,
 'address': '6001 Main St',
 'cards': [{'card_id': 9,
            'card_number': '4000000000000009',
            'card_type': 'discover'}],
 'email': 'katherine.johnson.7@example.com',
 'first_name': 'Katherine',
 'last_name': 'Johnson',
 'state_code': 'TX',
 'zipcode': '39999'}
```

The **filter** `{"_id": 7}` is a Python dict: "documents whose `_id` equals
7". What comes back is a dict too, with the customer's cards nested inside.
In SQLite, those cards were a second table and a join.

```python
print(db.customers.find_one({"_id": 99999}))
```

```text
None
```

No exception. **Always check for `None`** before indexing into the result,
or you'll get `TypeError: 'NoneType' object is not subscriptable` somewhere
later.

### 1.2 `find()` returns a cursor

```python
cursor = db.products.find()
print(type(cursor))
for product in cursor.limit(3):
    print(product)
```

```text
<class 'pymongo.synchronous.cursor.Cursor'>
{'_id': 1, 'product_name': 'Wireless Keyboard 0', 'unit_price': Decimal128('202.11')}
{'_id': 2, 'product_name': 'Portable Blender 1', 'unit_price': Decimal128('259.06')}
{'_id': 3, 'product_name': 'Adjustable Monitor 2', 'unit_price': Decimal128('398.52')}
```

A **cursor** is a lazy handle, not a list. Nothing is sent to the server
until you start iterating, and documents then arrive in batches. Two
consequences:

- A cursor can be iterated **once**. Wrap it in `list(...)` if you need the
  results twice. (Don't do that on a million documents.)
- You can keep adding `.sort()`, `.limit()`, `.skip()` to it *before* you
  iterate. Those calls just edit the request ([§3.4](#34-the-cursor-applies-sort-before-limit-no-matter-how-you-chain-them)).

### 1.3 Projections: ask for only the fields you need

"Show me some Books purchases: date, product, amount."

```python
query = {"department": "Books"}
projection = {"_id": 0, "purchase_date": 1, "product_name": 1, "amount": 1}

for p in db.purchases.find(query, projection).limit(3):
    print(p)
```

```text
{'amount': Decimal128('264.04'), 'purchase_date': datetime.datetime(2026, 5, 22, 0, 0), 'product_name': 'Stainless Lamp 5'}
{'amount': Decimal128('95.44'), 'purchase_date': datetime.datetime(2024, 9, 29, 0, 0), 'product_name': 'Insulated Blender 66'}
{'amount': Decimal128('296.80'), 'purchase_date': datetime.datetime(2025, 4, 26, 0, 0), 'product_name': 'Ceramic Keyboard 83'}
```

The second argument is the **projection**, SQL's `SELECT` list. The rules:

| Projection           | Meaning                                                         |
| -------------------- | --------------------------------------------------------------- |
| `{"a": 1, "b": 1}`   | **include** only `a`, `b`, and `_id`                            |
| `{"a": 0, "b": 0}`   | **exclude** `a` and `b`, keep everything else                   |
| `{"_id": 0, "a": 1}` | `_id` is the one field you may exclude in an include-projection |
| `{"a": 1, "b": 0}`   | **error**: you can't mix include and exclude (except `_id`)     |

`_id` comes back unless you say `"_id": 0`. An exclusion projection is handy
when a document has one big field you don't want:

```python
pprint(db.customers.find_one({"_id": 7}, {"cards": 0, "address": 0}))
```

```text
{'_id': 7,
 'email': 'katherine.johnson.7@example.com',
 'first_name': 'Katherine',
 'last_name': 'Johnson',
 'state_code': 'TX',
 'zipcode': '39999'}
```

A projection value starting with `$` means **"the value of that field"**,
which lets you rename (SQL's `AS`):

```python
print(db.purchases.find_one({}, {"_id": 0, "purchase_id": "$_id", "product": "$product_name"}))
```

```text
{'purchase_id': 1, 'product': 'Smart Speaker 65'}
```

That `"$field"` notation shows up everywhere in aggregation. Learn to read it
now: **a string starting with `$` is a field reference, not text.**

> **Exercise 1.** Write `customer_by_email(email)` that returns
> `"First Last (id N)"`, or a friendly message when no customer has that
> email. Test it with `katherine.johnson.7@example.com` and an address that
> doesn't exist.
>
> **Exercise 2.** List the first name, last name, and zipcode (no `_id`) of
> every customer in Texas. How many are there?

---

## Part 2 — Filter

### 2.1 Comparison operators

An operator is a dict **in the value position**: `{"field": {"$op": value}}`.

| Operator                | SQL                                                             | Operator       | SQL                  |
| ----------------------- | --------------------------------------------------------------- | -------------- | -------------------- |
| `$eq` (or just a value) | `=`                                                             | `$ne`          | `<>`                 |
| `$gt` / `$gte`          | `>` / `>=`                                                      | `$lt` / `$lte` | `<` / `<=`           |
| `$in`                   | `IN (...)`                                                      | `$nin`         | `NOT IN (...)`       |
| `$exists`               | `IS [NOT] NULL`, sort of ([§2.6](#26-missing-fields-and-typos)) | `$regex`       | `LIKE`, more or less |

"How many purchases were $390 or more?"

```python
print(db.purchases.count_documents({"amount": {"$gte": 390}}))
print(db.purchases.count_documents({"amount": {"$gte": Decimal128("390.00")}}))
```

```text
430
430
```

`amount` is `Decimal128` and `390` is an `int`, yet the comparison works.
MongoDB compares **all numeric types by value**. (Comparing a number to the
*string* `"390"` matches nothing. Types still matter.)

Two operators on one field form a **range**:

```python
cheap = {"unit_price": {"$gte": 20, "$lt": 30}}
for p in db.products.find(cheap, {"_id": 0, "product_name": 1, "unit_price": 1}):
    print(p)
```

```text
{'product_name': 'Premium Lamp 40', 'unit_price': Decimal128('23.65')}
{'product_name': 'Stainless Speaker 42', 'unit_price': Decimal128('26.58')}
{'product_name': 'Adjustable Blender 98', 'unit_price': Decimal128('29.68')}
```

### 2.2 Combine conditions: AND, OR, `$in`

**Several keys in one filter mean AND.** No operator needed:

```python
q_and = {"department": "Books", "state_code": "TX"}
print(db.purchases.count_documents(q_and))          # 3
```

**OR needs `$or`**, which takes a *list* of complete filters:

```python
q_or = {"$or": [{"state_code": "TX"}, {"amount": {"$gte": 395}}]}
print(db.purchases.count_documents(q_or))           # 535
```

When every branch tests the **same field for equality**, use `$in`. It's
shorter and easier for an index:

```python
q_in = {"department": {"$in": ["Books", "Music", "Movies"]}}
print(db.purchases.count_documents(q_in))           # 1416
```

> **Predict:** what does this filter match?
>
> ```python
> wrong = {"department": "Books", "department": "Music"}
> ```

<details>
<summary>Answer</summary>

```python
print(wrong)                                  # {'department': 'Music'}
print(db.purchases.count_documents(wrong))    # 459: just the Music purchases
```

A Python dict can't hold the same key twice: the second silently replaces
the first, before MongoDB ever sees it. There's no error and no warning.
"Books **or** Music" is `$in`. "Books **and** Music" is impossible for a
single-valued field.

</details>

### 2.3 Dates: use `datetime`, and a half-open range

"How many purchases happened in March 2025?"

```python
march = {"purchase_date": {"$gte": datetime(2025, 3, 1), "$lt": datetime(2025, 4, 1)}}
print(db.purchases.count_documents(march))          # 291
```

Two habits:

- **Compare dates to `datetime` objects, never strings.** `"2025-03-01"` is
  a string, and a string never equals or orders with a date.
  `{"purchase_date": {"$gte": "2025-03-01"}}` silently matches nothing.
- **Inclusive start, exclusive end** (`$gte` … `$lt`). "Before April 1"
  needs no knowledge of how many days March has or what time the last
  purchase was. It works the same for days, months, and years.

PyMongo treats a `datetime` without a timezone as UTC, which is how these
dates were stored.

### 2.4 Nested fields and arrays

Reach into an embedded document with **dot notation**, in quotes:

```python
print(db.customers.count_documents({"cards.card_type": "visa"}))        # 56
```

`cards` is an *array*, so `"cards.card_type": "visa"` means "**some** card
in the array is a visa". MongoDB tests each element for you. More array
operators:

```python
print(db.customers.count_documents({"cards": {"$size": 2}}))            # 225: exactly two cards
print(db.customers.count_documents(
    {"cards.card_type": {"$all": ["visa", "mastercard"]}}))             # 8: holds both
```

### 2.5 The array trap, and `$elemMatch`

> **Predict:** card ids are integers. How many customers have a card whose
> id is strictly between 100 and 101?
>
> ```python
> between = {"cards.card_id": {"$gt": 100, "$lt": 101}}
> ```

<details>
<summary>Answer</summary>

You'd say zero. MongoDB says one:

```python
for c in db.customers.find(between, {"cards.card_id": 1}):
    print(c)
```

```text
{'_id': 68, 'cards': [{'card_id': 100}, {'card_id': 101}]}
```

On an array, **each condition only has to be true for *some* element, not
the same one**. Card 101 satisfies `$gt: 100`; card 100 satisfies
`$lt: 101`. Customer 68 matches.

`$elemMatch` says "one element must satisfy **all** of these":

```python
between = {"cards": {"$elemMatch": {"card_id": {"$gt": 100, "$lt": 101}}}}
print(list(db.customers.find(between)))       # []
```

The same trap applies to conditions on two *different* fields of the
elements: `{"cards.card_type": "visa", "cards.card_id": 9}` matches a
customer whose visa is card 12 and whose discover is card 9. Use `$elemMatch`
whenever "the same element" matters.

</details>

### 2.6 Missing fields, and typos

```python
print(db.customers.count_documents({"phone": {"$exists": True}}))   # 0: no customer has one
print(db.purchases.count_documents({"departmnet": "Books"}))        # 0: a typo, not an error
```

MongoDB has no schema to check a field name against, so a misspelled field
is simply a field no document has. **A surprising 0 is your cue to check
spelling**, in field names and collection names alike (`db.purchasez`
"exists" too).

Two filters look alike but aren't:

| Filter                          | Matches                                              |
| ------------------------------- | ---------------------------------------------------- |
| `{"phone": {"$exists": False}}` | documents with no `phone` field at all               |
| `{"phone": None}`               | documents with no `phone` field **or** `phone: null` |

> **Exercise 3.** How many purchases were between $100 and $150, inclusive?
>
> **Exercise 4.** Find purchases in Books or Music, made in Texas, for under
> $100. Show `_id`, department, and amount.
>
> **Exercise 5.** How many purchases were in the first quarter of 2026? Write
> it with a half-open range. Then write it with `$lte: datetime(2026, 3, 31)`
> and explain why that version works *in this database* but would be a bug
> if `purchase_date` stored times of day.
>
> **Exercise 6.** How many customers hold a visa **or** a mastercard? How many
> customers in California have exactly one card?

---

## Part 3 — Sort, limit, page, count

### 3.1 Sort and limit

"What are our five most expensive products?"

```python
cursor = (
    db.products
    .find({}, {"_id": 1, "product_name": 1, "unit_price": 1})
    .sort("unit_price", DESCENDING)
    .limit(5)
)
for p in cursor:
    print(p)
```

```text
{'_id': 12, 'product_name': 'Insulated Tripod 11', 'unit_price': Decimal128('399.31')}
{'_id': 92, 'product_name': 'Ergonomic Backpack 91', 'unit_price': Decimal128('398.82')}
{'_id': 3, 'product_name': 'Adjustable Monitor 2', 'unit_price': Decimal128('398.52')}
{'_id': 98, 'product_name': 'Premium Speaker 97', 'unit_price': Decimal128('396.21')}
{'_id': 27, 'product_name': 'Classic Kettle 26', 'unit_price': Decimal128('383.20')}
```

`DESCENDING` is just `-1` and `ASCENDING` is `1`. For more than one key, pass
a **list of tuples**. (`mongosh` writes `{unit_price: -1}`. PyMongo wants a
list, because the order of the keys is the meaning.)

```python
.sort([("purchase_date", DESCENDING), ("_id", DESCENDING)])
```

**Without a `sort`, there is no order.** Documents come back in whatever
order the server found them in, usually insertion order, until it isn't.
Never rely on it.

### 3.2 Ties, and why every sort needs a tie-breaker

"Show the 12 most recent purchases":

```python
latest = (db.purchases.find({}, {"purchase_date": 1, "amount": 1})
          .sort("purchase_date", DESCENDING).limit(12))
```

```text
{'_id': 6036, 'amount': Decimal128('78.93'),  'purchase_date': datetime.datetime(2026, 8, 31, 0, 0)}
{'_id': 8661, 'amount': Decimal128('95.44'),  'purchase_date': datetime.datetime(2026, 8, 30, 0, 0)}
{'_id': 7449, 'amount': Decimal128('98.21'),  'purchase_date': datetime.datetime(2026, 8, 30, 0, 0)}
... nine more, all on 2026-08-30 ...
```

Eleven purchases share **2026-08-30**. The sort says nothing about their
order relative to each other, so the server may return them in any order,
and a different order the next time (after an index change, a restart, a
bigger collection). For one screenful that's cosmetic. For **paging** it's a
bug: a tied row can show up on page 1 *and* page 2, or on neither.

The fix is a final sort key that's **unique**, usually `_id`:

```python
.sort([("purchase_date", DESCENDING), ("_id", DESCENDING)])
```

Now every document has exactly one position. Make this a reflex: **the last
sort key is unique.**

### 3.3 Paging: `skip` vs keyset

Page 3, five per page, the obvious way:

```python
page_size, page = 5, 3
for p in (db.purchases.find({}, {"amount": 1})
          .sort("_id", ASCENDING)
          .skip((page - 1) * page_size)
          .limit(page_size)):
    print(p)
```

```text
{'_id': 11, 'amount': Decimal128('88.44')}
...
{'_id': 15, 'amount': Decimal128('383.20')}
```

`skip(10)` still **walks past** the first 10 documents. Page 2,000 walks past
10,000. The cost grows with the page number (that's Q11 in the catalog).

**Keyset** paging remembers where the last page ended and asks for what
comes after it:

```python
last_seen = 10            # the last _id on page 2
for p in (db.purchases.find({"_id": {"$gt": last_seen}}, {"amount": 1})
          .sort("_id", ASCENDING)
          .limit(page_size)):
    print(p)              # the same five documents
```

With an index on the sort key, that's a jump straight to the right spot,
however deep the page. The price: you can only go to the *next* page, not
straight to page 2,000. (When the sort has two keys, the "after" filter
needs both. That's Exercise 8.)

### 3.4 The cursor applies sort before limit, no matter how you chain them

```python
a = [p["_id"] for p in db.products.find().limit(5).sort("unit_price", DESCENDING)]
b = [p["_id"] for p in db.products.find().sort("unit_price", DESCENDING).limit(5)]
print(a == b, a)
```

```text
True [12, 92, 3, 98, 27]
```

On a `find()` cursor, `.sort()`, `.skip()`, and `.limit()` are **settings**,
not steps. The server always sorts, then skips, then limits. Remember this:
in an aggregation pipeline ([Part 4](#part-4--the-aggregation-pipeline)),
**order is everything**.

### 3.5 Counting and distinct values

```python
print(db.purchases.count_documents({"department": "Books"}))   # 464: exact, applies a filter
print(db.purchases.estimated_document_count())                  # 10000: whole collection, from metadata, instant
print(db.purchases.distinct("department")[:5])                  # ['Automotive', 'Baby', 'Beauty', 'Books', 'Clothing']
```

- `count_documents(filter)` counts matches exactly. `count_documents({})`
  is exact too, but has to count.
- `estimated_document_count()` reads the collection's metadata. Use it for
  "about how big is this?"
- `distinct(field)` returns a Python list of the unique values (22
  departments here). On an array field it unwinds the array:
  `db.customers.distinct("cards.card_type")` lists card types.

> **Exercise 7.** Show the three cheapest products, with product name as a
> secondary sort.
>
> **Exercise 8.** Customer 74 has more than a thousand purchases. Show page 4
> of their history, 10 per page, newest first, using `skip`. Then get the
> same page with **keyset** paging: given the last document of page 3, write
> the filter for "after it" when the sort is `purchase_date DESC, _id DESC`.
> (Hint: "earlier date, **or** same date and smaller `_id`.") Check that both
> versions return the same ten documents.

---

## Part 4 — The aggregation pipeline

`find()` returns documents that exist. The moment the question is "how
many", "how much", "per what", or "compared with what", you need documents
that **don't exist yet**, computed from the ones that do. That's
**aggregation**.

### 4.1 The mental model: an assembly line

A pipeline is a **Python list of stages**. Documents enter at the top, and
each stage receives the previous stage's output, transforms it, and passes
it on:

```text
purchases (10,000 docs)
   │
   ▼  {"$match": {"department": "Books"}}          filter          → 464 purchase docs
   ▼  {"$group": {"_id": "$state_code", ...}}       collapse        → 50 docs, one per state
   ▼  {"$sort": {"revenue": -1}}                    reorder         → 50 docs, best first
   ▼  {"$limit": 3}                                 cut             → 3 docs
   │
   ▼  your Python code
```

Three ideas carry the rest of this handout:

1. **Order matters.** A stage only sees what the previous stage produced.
   (Unlike `find()`'s cursor settings, [§3.4](#34-the-cursor-applies-sort-before-limit-no-matter-how-you-chain-them).)
2. **Shapes change.** After a `$group`, the original fields are *gone*. Only
   the group key and what you computed exist. After `$project`, only what you
   kept exists. Most pipeline bugs are a stage referring to a field that an
   earlier stage removed.
3. **A stage can appear more than once.** `$match` before `$group` is SQL's
   `WHERE`; `$match` after it is `HAVING`. Two `$group`s answer "group, then
   group the groups."

### 4.2 SQL clause ↔ pipeline stage

| SQL                             | Stage                                          | Notes                          |
| ------------------------------- | ---------------------------------------------- | ------------------------------ |
| `FROM purchases`                | `db.purchases.aggregate(...)`                  | the collection you start from  |
| `WHERE`                         | `$match`                                       | same filter syntax as `find()` |
| `GROUP BY` + aggregates         | `$group`                                       | `_id` is the group key         |
| `HAVING`                        | `$match` after `$group`                        | filters groups, not documents  |
| `SELECT a, b AS c`, expressions | `$project`, `$set` / `$addFields`              | reshape, rename, compute       |
| `ORDER BY`                      | `$sort`                                        |                                |
| `LIMIT` / `OFFSET`              | `$limit` / `$skip`                             |                                |
| `count(*)`                      | `$count` stage, or `{"$sum": 1}` in a `$group` |                                |
| `JOIN`                          | `$lookup`                                      | produces an **array**          |
| `ROW_NUMBER()`, `SUM() OVER`    | `$setWindowFields`                             |                                |
| *(no equivalent)*               | `$unwind`                                      | one document per array element |

### 4.3 Your first pipeline

"How many Books purchases?"

```python
pipeline = [
    {"$match": {"department": "Books"}},
    {"$count": "num_purchases"},
]
print(list(db.purchases.aggregate(pipeline)))
```

```text
[{'num_purchases': 464}]
```

`aggregate()` returns a cursor, like `find()`; `list()` drains it. The result
is a list of documents, here a list of one. (`count_documents` would have
done this. Pipelines earn their keep from Part 5 on.)

### 4.4 Build pipelines one stage at a time

The best debugging technique for pipelines is to **run a prefix**: the first
stage, then the first two, and so on, and look at the shape after each.

```python
pipeline = [
    {"$match": {"department": "Books"}},
    {"$group": {"_id": "$state_code", "revenue": {"$sum": "$amount"}}},
    {"$sort": {"revenue": -1}},
    {"$limit": 3},
]
for k in range(1, len(pipeline) + 1):
    out = list(db.purchases.aggregate(pipeline[:k]))
    print(k, len(out), out[0])
```

```text
1 464 {'_id': 3, 'customer_id': 74, 'card_id': 108, 'product_id': 6, 'department': 'Books', 'amount': Decimal128('264.04'), ...}
2 50 {'_id': 'CA', 'revenue': Decimal128('2651.85')}
3 50 {'_id': 'HI', 'revenue': Decimal128('14616.19')}
4 3 {'_id': 'HI', 'revenue': Decimal128('14616.19')}
```

Read it as a story: 464 purchase documents, collapsed into 50 state
documents (`customer_id`, `amount`, and the rest are gone), sorted, cut to 3.
**When a pipeline gives a wrong answer, this loop shows you which stage went
wrong.**

---

## Part 5 — Group

### 5.1 `$group` anatomy

```python
{"$group": {
    "_id": <group key>,                       # what makes two documents "the same group"
    "<output field>": {<accumulator>: <expression>},
    "<output field>": {<accumulator>: <expression>},
}}
```

- `_id` is **required** and is the group key: one output document per
  distinct value. `None` means "everything in one group".
- Every other field is computed by an **accumulator** over the group's
  documents.
- **Nothing else survives.** A field you don't name in `$group` is not in its
  output.

### 5.2 One group: totals for the whole collection

```python
pipeline = [
    {"$group": {
        "_id": None,
        "num_purchases": {"$sum": 1},
        "revenue": {"$sum": "$amount"},
        "avg_amount": {"$avg": "$amount"},
        "smallest": {"$min": "$amount"},
        "largest": {"$max": "$amount"},
        "first_day": {"$min": "$purchase_date"},
        "last_day": {"$max": "$purchase_date"},
    }},
]
pprint(list(db.purchases.aggregate(pipeline)))
```

```text
[{'_id': None,
  'avg_amount': Decimal128('219.476634'),
  'first_day': datetime.datetime(2024, 1, 1, 0, 0),
  'largest': Decimal128('399.31'),
  'last_day': datetime.datetime(2026, 8, 31, 0, 0),
  'num_purchases': 10000,
  'revenue': Decimal128('2194766.34'),
  'smallest': Decimal128('10.92')}]
```

Read the two `$sum`s carefully, because they're the most common accumulator
confusion:

| Expression            | Means                                                  | SQL           |
| --------------------- | ------------------------------------------------------ | ------------- |
| `{"$sum": 1}`         | add **1** for each document                            | `count(*)`    |
| `{"$sum": "$amount"}` | add **the value of `amount`** for each document        | `sum(amount)` |
| `{"$sum": "amount"}`  | add the *string* "amount": not a number, contributes 0 | a bug         |

Forgetting the `$` gives you `0`, not an error. `$min`/`$max` work on dates
and strings as well as numbers.

### 5.3 Group by a field

"Revenue by department":

```python
pipeline = [
    {"$group": {
        "_id": "$department",
        "num_purchases": {"$sum": 1},
        "revenue": {"$sum": "$amount"},
    }},
]
for row in db.purchases.aggregate(pipeline):
    print(row)
```

```text
{'_id': 'Electronics', 'num_purchases': 496, 'revenue': Decimal128('108777.50')}
{'_id': 'Automotive', 'num_purchases': 463, 'revenue': Decimal128('104935.77')}
{'_id': 'Toys', 'num_purchases': 435, 'revenue': Decimal128('97545.72')}
{'_id': 'Games', 'num_purchases': 463, 'revenue': Decimal128('104501.04')}
...
```

`"_id": "$department"`: one group per distinct value of `department`, and the
output's `_id` *is* that value. The SQL:

```sql
SELECT department, count(*) AS num_purchases, sum(amount) AS revenue
FROM purchases GROUP BY department;
```

Notice the output is in **no particular order**. `$group` doesn't sort, any
more than SQL's `GROUP BY` promises to.

### 5.4 Sort the groups

"Top five departments by revenue":

```python
pipeline = [
    {"$group": {
        "_id": "$department",
        "num_purchases": {"$sum": 1},
        "revenue": {"$sum": "$amount"},
    }},
    {"$sort": {"revenue": -1, "_id": 1}},
    {"$limit": 5},
]
```

```text
{'_id': 'Electronics', 'num_purchases': 496, 'revenue': Decimal128('108777.50')}
{'_id': 'Automotive', 'num_purchases': 463, 'revenue': Decimal128('104935.77')}
{'_id': 'Movies', 'num_purchases': 493, 'revenue': Decimal128('104569.89')}
{'_id': 'Games', 'num_purchases': 463, 'revenue': Decimal128('104501.04')}
{'_id': 'Music', 'num_purchases': 459, 'revenue': Decimal128('104488.24')}
```

Things to notice:

- **`$sort` sorts on fields that exist *at that point***: `revenue` was
  invented by `$group` one stage earlier. Sorting on `amount` here would sort
  on a field no document has anymore. That's legal and silently useless.
- Inside a pipeline, `$sort` takes a **dict** (`{"revenue": -1, "_id": 1}`),
  not the list of tuples `find().sort()` wants. Python dicts keep insertion
  order, so the first key is the primary sort.
- `"_id": 1` is the **tie-breaker** ([§3.2](#32-ties-and-why-every-sort-needs-a-tie-breaker)).
  After a `$group`, `_id` is the group key, unique by definition, so it's
  always a safe last key.
- `$sort` immediately followed by `$limit` is optimized into a **top-k**: the
  server keeps only the best 5 while it sorts, instead of sorting all 22.

Sorting by count is so common there's a shortcut stage: group, count, and
sort descending in one:

```python
db.purchases.aggregate([{"$sortByCount": "$department"}, {"$limit": 3}])
```

```text
{'_id': 'Electronics', 'count': 496}
{'_id': 'Movies', 'count': 493}
{'_id': 'Beauty', 'count': 490}
```

### 5.5 Make the output presentable: `$project`

`_id` is an awkward name for "department", and averages have too many
digits. Add a `$project` at the end:

```python
pipeline = [
    {"$group": {
        "_id": "$department",
        "num_purchases": {"$sum": 1},
        "revenue": {"$sum": "$amount"},
        "avg_amount": {"$avg": "$amount"},
    }},
    {"$sort": {"revenue": -1, "_id": 1}},
    {"$limit": 5},
    {"$project": {
        "_id": 0,
        "department": "$_id",
        "num_purchases": 1,
        "revenue": {"$round": ["$revenue", 2]},
        "avg_amount": {"$round": ["$avg_amount", 2]},
    }},
]
```

```text
{'num_purchases': 496, 'department': 'Electronics', 'revenue': Decimal128('108777.50'), 'avg_amount': Decimal128('219.31')}
{'num_purchases': 463, 'department': 'Automotive', 'revenue': Decimal128('104935.77'), 'avg_amount': Decimal128('226.64')}
...
```

`$project` is the same projection language as `find()`, plus **expressions**
(`$round`, `$concat`, `$multiply`, `$cond`, ...). Its sibling `$set` (alias
`$addFields`) adds or replaces fields and **keeps all the others**. Use
`$set` when you want to add one field, and `$project` when you want to
decide the whole shape.

Why put `$project` *last*? Because `$sort` used `_id` as the tie-breaker. Had
we renamed it first, the sort would need `"department": 1` instead. Either
works, as long as each stage uses the names that exist at that point.

### 5.6 The accumulator toolbox

| Accumulator                            | Result per group                                                     | Order-sensitive? |
| -------------------------------------- | -------------------------------------------------------------------- | :--------------: |
| `$sum`, `$avg`                         | total, mean                                                          |        no        |
| `$min`, `$max`                         | smallest, largest                                                    |        no        |
| `$count` (`{"$count": {}}`)            | number of documents, same as `{"$sum": 1}`                           |        no        |
| `$push`                                | list of every value, duplicates included                             |     **yes**      |
| `$addToSet`                            | list of distinct values, no guaranteed order                         |        no        |
| `$first`, `$last`                      | the value from the first/last document **in the order they arrived** |     **yes**      |
| `$top`, `$bottom`, `$topN`, `$bottomN` | first/last by a sort you give **inside the accumulator**             |        no        |

"Customer 7's history, summarized":

```python
pipeline = [
    {"$match": {"customer_id": 7}},
    {"$group": {
        "_id": "$customer_id",
        "first_purchase": {"$min": "$purchase_date"},
        "last_purchase": {"$max": "$purchase_date"},
        "departments": {"$addToSet": "$department"},
        "amounts": {"$push": "$amount"},
    }},
]
```

```text
[{'_id': 7,
  'amounts': [Decimal128('264.04'), Decimal128('203.53'), Decimal128('246.04'), ... 13 values],
  'departments': ['Games', 'Industrial', 'Baby', 'Clothing', 'Shoes', 'Tools',
                  'Music', 'Kids', 'Books', 'Movies'],
  'first_purchase': datetime.datetime(2024, 2, 21, 0, 0),
  'last_purchase': datetime.datetime(2026, 8, 30, 0, 0)}]
```

13 purchases, 10 distinct departments. Use `$push` with care: a group's
output is one document, and a document can't exceed **16 MB**. Pushing every
purchase of customer 74 at 1m scale gets close.

**`$first` and `$last` depend on order.** Without a `$sort` before the
`$group`, "first" means "whichever arrived first", which is arbitrary. To get
customer 7's first and latest *products*:

```python
pipeline = [
    {"$match": {"customer_id": 7}},
    {"$sort": {"purchase_date": 1, "_id": 1}},          # define "first"
    {"$group": {
        "_id": "$customer_id",
        "first_product": {"$first": "$product_name"},
        "latest_product": {"$last": "$product_name"},
    }},
]
```

```text
[{'_id': 7, 'first_product': 'Stainless Lamp 5', 'latest_product': 'Classic Kettle 26'}]
```

For dates you didn't need this: `$min`/`$max` don't care about order. You
need sort-then-`$first` when you want **another field from** the
first/last document. [Part 7](#part-7--sorting-inside-a-pipeline) builds on
exactly that.

> **Exercise 9.** Which three customers have the highest *average* purchase
> amount? Show the customer id and the average rounded to 2 places.
>
> **Exercise 10.** Write the SQL for the 5.5 pipeline. Then, without running
> it, explain what changes if you move the `$project` stage to the top, right
> after `$group`, and leave everything else alone.

---

## Part 6 — Group by anything

The group key `_id` can be **any expression**: a field, a sub-document of
several fields, or a computed value.

### 6.1 Several keys: a compound `_id`

"Revenue by state *and* department":

```python
pipeline = [
    {"$group": {
        "_id": {"state": "$state_code", "department": "$department"},
        "num_purchases": {"$sum": 1},
        "revenue": {"$sum": "$amount"},
    }},
    {"$sort": {"_id.state": 1, "revenue": -1}},
    {"$limit": 3},
]
```

```text
{'_id': {'state': 'AK', 'department': 'Shoes'}, 'num_purchases': 13, 'revenue': Decimal128('2815.43')}
{'_id': {'state': 'AK', 'department': 'Movies'}, 'num_purchases': 15, 'revenue': Decimal128('2783.67')}
{'_id': {'state': 'AK', 'department': 'Music'}, 'num_purchases': 14, 'revenue': Decimal128('2767.52')}
```

That's SQL's `GROUP BY state_code, department`. The key is now a
sub-document, so later stages reach into it with dot notation:
`"_id.state"`. The sort reads "state A→Z, and within a state, revenue high to
low".

A **flattening `$project`** is almost always the next stage, so the result
looks like rows again:

```python
    {"$project": {
        "_id": 0,
        "state": "$_id.state",
        "department": "$_id.department",
        "revenue": 1,
    }},
```

```text
{'revenue': Decimal128('2815.43'), 'state': 'AK', 'department': 'Shoes'}
```

### 6.2 Computed keys: group by month, weekday, year

There's no `month` field, so group by an **expression** that computes one
from `purchase_date`:

```python
pipeline = [
    {"$group": {
        "_id": {"$dateToString": {"format": "%Y-%m", "date": "$purchase_date"}},
        "revenue": {"$sum": "$amount"},
    }},
    {"$sort": {"_id": 1}},
]
```

```text
{'_id': '2024-01', 'revenue': Decimal128('70521.68')}
{'_id': '2024-02', 'revenue': Decimal128('70217.53')}
{'_id': '2024-03', 'revenue': Decimal128('69783.42')}
...
```

`"%Y-%m"` strings sort correctly as text, which is why the format puts the
year first. `{"$dateTrunc": {"date": "$purchase_date", "unit": "month"}}`
does the same and keeps a real date (useful in [Part 9](#part-9--beyond-group)).
Other date parts make other questions:

```python
"_id": {"$year": "$purchase_date"}          # revenue by year
"_id": {"$dayOfWeek": "$purchase_date"}     # 1 = Sunday ... 7 = Saturday
```

```text
{'_id': 2, 'num_purchases': 1447}        # by weekday: almost perfectly flat,
{'_id': 3, 'num_purchases': 1442}        # which is how you can tell the data is generated
...
```

### 6.3 Ranges: `$bucket`

"How are purchase amounts distributed?" Grouping by `amount` itself would give
hundreds of tiny groups. `$bucket` groups by **range**:

```python
pipeline = [
    {"$bucket": {
        "groupBy": "$amount",
        "boundaries": [0, 50, 100, 200, 300, 400],
        "output": {"num_purchases": {"$sum": 1}},
    }},
]
```

```text
{'_id': 0, 'num_purchases': 528}          # [0, 50)
{'_id': 50, 'num_purchases': 1951}        # [50, 100)
{'_id': 100, 'num_purchases': 1556}       # [100, 200)
{'_id': 200, 'num_purchases': 3584}       # [200, 300)
{'_id': 300, 'num_purchases': 2381}       # [300, 400)
```

Each bucket is named by its lower bound and is half-open, like the date
ranges in [§2.3](#23-dates-use-datetime-and-a-half-open-range). A value
outside every boundary is an **error** unless you add `"default": "other"`.

### 6.4 WHERE vs HAVING: `$match` before and after `$group`

"Which customers made at least 100 purchases?" That's a condition on a
*group*, so the `$match` goes **after** the `$group`:

```python
pipeline = [
    {"$group": {
        "_id": "$customer_id",
        "num_purchases": {"$sum": 1},
        "spent": {"$sum": "$amount"},
    }},
    {"$match": {"num_purchases": {"$gte": 100}}},       # HAVING count(*) >= 100
    {"$sort": {"num_purchases": -1}},
]
```

```text
{'_id': 74, 'num_purchases': 1294, 'spent': Decimal128('283974.21')}
{'_id': 418, 'num_purchases': 385, 'spent': Decimal128('88578.47')}
...
{'_id': 201, 'num_purchases': 116, 'spent': Decimal128('24398.68')}
{'_id': 290, 'num_purchases': 116, 'spent': Decimal128('25587.07')}
```

Customer 74 alone has 13% of all purchases. The generator skews the data on
purpose, and the unit's §7 and §8 lean on it.

Notice the last two rows: customers 201 and 290 **tie** at 116, and this sort
has no tie-breaker, so their order isn't guaranteed. Add `"_id": 1`.

Both kinds of `$match` in one pipeline, "customers with 5+ Books purchases":

```python
pipeline = [
    {"$match": {"department": "Books"}},                  # WHERE: filters purchases
    {"$group": {"_id": "$customer_id", "n": {"$sum": 1}}},
    {"$match": {"n": {"$gte": 5}}},                        # HAVING: filters customers
    {"$count": "customers"},
]
```

```text
[{'customers': 12}]
```

> **Predict:** what happens if you swap the two `$match` stages?

<details>
<summary>Answer</summary>

The first `$match` now asks for purchases with a field `n` ≥ 5. No purchase
has an `n`, so nothing survives, and you get `[]`. Nothing errors. Then the
second `$match` would ask groups for `department`, which `$group` dropped.
**A filter belongs before the `$group` if it's about documents, and after it
if it's about groups.** A filter about documents also belongs as *early* as
possible, so fewer documents travel down the line and an index can find them
([Part 10](#part-10--is-it-fast)).

</details>

> **Exercise 11.** Average purchase amount by state, for states with at
> least 400 purchases, highest average first, rounded to 2 places, with the
> field named `state` instead of `_id`.
>
> **Exercise 12.** Number of purchases and revenue by year.

---

## Part 7 — Sorting inside a pipeline

In a pipeline, `$sort` isn't only for the final output. Sorting **before** a
`$group` decides what `$first` and `$last` see, and that's how you answer
**"the best X in each Y"**, one of the most common report questions there is.

### 7.1 Top one per group: sort, then group again

"What's the best-selling department in each state?"

```python
pipeline = [
    # 1. one document per (state, department) with its revenue
    {"$group": {
        "_id": {"state": "$state_code", "department": "$department"},
        "revenue": {"$sum": "$amount"},
    }},
    # 2. within each state, best department first
    {"$sort": {"_id.state": 1, "revenue": -1, "_id.department": 1}},
    # 3. one document per state; $first takes the best, because of step 2
    {"$group": {
        "_id": "$_id.state",
        "best_department": {"$first": "$_id.department"},
        "revenue": {"$first": "$revenue"},
    }},
    {"$sort": {"_id": 1}},
]
```

```text
{'_id': 'AK', 'best_department': 'Shoes', 'revenue': Decimal128('2815.43')}
{'_id': 'AL', 'best_department': 'Computers', 'revenue': Decimal128('3779.77')}
{'_id': 'AR', 'best_department': 'Automotive', 'revenue': Decimal128('2289.21')}
{'_id': 'AZ', 'best_department': 'Music', 'revenue': Decimal128('3026.23')}
{'_id': 'CA', 'best_department': 'Computers', 'revenue': Decimal128('4491.54')}
...
```

Trace the shapes: 10,000 purchases → 1,102 (state, department)
documents → sorted → 50 state documents. The second `$group` groups **the
output of the first**: its `$_id.state` refers to the compound key the first
`$group` built.

`_id.department` in the sort is the tie-breaker: if two departments in a
state had exactly equal revenue, it decides which one counts as "best",
every time.

In SQL this is a window function:
`ROW_NUMBER() OVER (PARTITION BY state_code ORDER BY revenue DESC) = 1`.

### 7.2 Top N per group: `$topN`

For the top **two** per state, `$first` isn't enough. `$topN` carries its
own sort, so it doesn't depend on the order documents arrive in:

```python
pipeline = [
    {"$group": {
        "_id": {"state": "$state_code", "department": "$department"},
        "revenue": {"$sum": "$amount"},
    }},
    {"$group": {
        "_id": "$_id.state",
        "top2": {"$topN": {
            "n": 2,
            "sortBy": {"revenue": -1, "_id.department": 1},
            "output": {"department": "$_id.department", "revenue": "$revenue"},
        }},
    }},
    {"$sort": {"_id": 1}},
]
```

```text
{'_id': 'AK',
 'top2': [{'department': 'Shoes', 'revenue': Decimal128('2815.43')},
          {'department': 'Movies', 'revenue': Decimal128('2783.67')}]}
{'_id': 'AL',
 'top2': [{'department': 'Computers', 'revenue': Decimal128('3779.77')},
          {'department': 'Jewelry', 'revenue': Decimal128('3302.21')}]}
```

No `$sort` stage between the groups. Prefer `$top`/`$topN` in new code: the
order is part of the accumulator, so moving stages around can't break it.

### 7.3 Grouping twice: statistics of groups

"On average, how many purchases does a customer make?" That's a group (per
customer) and then a summary *of the groups*:

```python
pipeline = [
    {"$group": {"_id": "$customer_id", "n": {"$sum": 1}}},
    {"$group": {
        "_id": None,
        "customers": {"$sum": 1},
        "avg_purchases": {"$avg": "$n"},
        "most": {"$max": "$n"},
        "fewest": {"$min": "$n"},
    }},
]
```

```text
[{'_id': None, 'customers': 450, 'avg_purchases': 22.22222222222222, 'most': 1294, 'fewest': 2}]
```

An average of 22, a maximum of 1,294: the mean hides the skew completely.
Also notice **450**, not 500. Fifty customers never bought anything, so they
never appear in `purchases` and can't be counted from it. (Exercise 15 finds
them.)

> **Exercise 13.** For each department, which product was bought most often?
> Show the first five departments alphabetically. Then look at the answer and
> explain what it tells you about the data.

---

## Part 8 — Arrays and other collections

### 8.1 `$unwind`: one document per array element

To group by something **inside an array**, first turn the array into
separate documents:

```python
print(db.customers.count_documents({}))                                       # 500
print(list(db.customers.aggregate([{"$unwind": "$cards"}, {"$count": "docs"}])))  # [{'docs': 725}]
```

```text
before $unwind:  {_id: 7,  ..., cards: [card 9]}
                 {_id: 68, ..., cards: [card 100, card 101]}

after $unwind:   {_id: 7,  ..., cards: card 9}
                 {_id: 68, ..., cards: card 100}
                 {_id: 68, ..., cards: card 101}      ← same _id twice
```

Each output document is a copy of the customer with `cards` replaced by
**one** card. 275 customers with one card and 225 with two make
275 + 450 = 725 documents. Now `"$cards.card_type"` is a single value you can
group by:

```python
pipeline = [
    {"$unwind": "$cards"},
    {"$group": {"_id": "$cards.card_type", "cards_held": {"$sum": 1}}},
    {"$sort": {"cards_held": -1, "_id": 1}},
    {"$limit": 5},
]
for row in db.customers.aggregate(pipeline):
    print(row)
```

```text
{'_id': 'americanexpress', 'cards_held': 65}
{'_id': 'switch', 'cards_held': 64}
{'_id': 'jcb', 'cards_held': 61}
{'_id': 'mastercard', 'cards_held': 61}
{'_id': 'china-unionpay', 'cards_held': 60}
```

Compare cards **used**, from the copied `card_type` on purchases:

```python
pipeline = [
    {"$group": {"_id": "$card_type", "times_used": {"$sum": 1}}},
    {"$sort": {"times_used": -1, "_id": 1}},
    {"$limit": 5},
]
```

```text
{'_id': 'switch', 'times_used': 1265}
{'_id': 'maestro', 'times_used': 1234}
...
```

Different questions, different collections, different answers. Two warnings
about `$unwind`:

- **After `$unwind`, counting documents no longer counts customers.**
  `{"$sum": 1}` above counts *cards*. To count customers, group by `_id`
  again, or use `$size` on the array without unwinding.
- **A customer with an empty or missing `cards` disappears** from the output.
  Use `{"$unwind": {"path": "$cards", "preserveNullAndEmptyArrays": True}}` to
  keep them.

### 8.2 `$lookup`: bring in a document from another collection

"Who are our top three customers, **by name**?" `purchases` has
`customer_id` but no name, so look the customer up:

```python
pipeline = [
    {"$group": {"_id": "$customer_id", "spent": {"$sum": "$amount"}}},
    {"$sort": {"spent": -1, "_id": 1}},
    {"$limit": 3},
    {"$lookup": {
        "from": "customers",        # the other collection
        "localField": "_id",        # field in *this* pipeline's documents (the customer id)
        "foreignField": "_id",      # field in customers to match it against
        "as": "customer",           # name of the new field
    }},
]
pprint(list(db.purchases.aggregate(pipeline))[0])
```

```text
{'_id': 74,
 'customer': [{'_id': 74,
               'address': '4974 Main St',
               'cards': [...],
               'email': 'bjarne.lamport.74@example.com',
               'first_name': 'Bjarne',
               'last_name': 'Lamport',
               'state_code': 'HI',
               'zipcode': '50618'}],
 'spent': Decimal128('283974.21')}
```

`$lookup` always produces an **array**, here holding exactly one customer,
because there's no way for it to know there's only one match. `$unwind` it
to get a plain sub-document, then `$project` the fields you want:

```python
    {"$unwind": "$customer"},
    {"$project": {
        "_id": 0,
        "customer_id": "$_id",
        "name": {"$concat": ["$customer.first_name", " ", "$customer.last_name"]},
        "state": "$customer.state_code",
        "spent": 1,
    }},
```

```text
{'spent': Decimal128('283974.21'), 'customer_id': 74, 'name': 'Bjarne Lamport', 'state': 'HI'}
{'spent': Decimal128('88578.47'), 'customer_id': 418, 'name': 'Anita Lamport', 'state': 'KY'}
{'spent': Decimal128('48221.82'), 'customer_id': 23, 'name': 'Bjarne Goldwasser', 'state': 'LA'}
```

**Where the `$lookup` sits matters.** It comes *after* `$group`, `$sort`, and
`$limit`, so it runs **3** times. Put it first, and it runs once per
purchase, 10,000 times, to fetch names for rows that are then thrown away.
**Narrow first, then join.**

Two more `$lookup` facts:

- The fields must match **in type**. An `int` 74 doesn't match a string
  `"74"`, and an `ObjectId` doesn't match its hex string. A mismatch gives
  empty arrays, not an error.
- `$lookup` is a join *you* write, every time. The [§4](04_model/) design
  copies `state_code` and `product_name` into each purchase precisely so most
  queries don't need one.

> **Exercise 14.** The top 5 customers in Texas by amount spent, with their
> full names and number of purchases.
>
> **Exercise 15.** Fifty customers have never bought anything. Find them with
> a `$lookup` that starts from `customers`. (What does the `as` array look
> like for a customer with no purchases?) Then confirm the count with
> `distinct` and a subtraction.
>
> **Exercise 16.** After `{"$unwind": "$cards"}`, write two stages that
> count **customers** again, not cards. Why does the answer equal
> `count_documents({})` in this database, and when wouldn't it?

---

## Part 9 — Beyond `$group`

Two more stages worth knowing exist. The query catalog uses both.

### 9.1 Window functions: `$setWindowFields`

`$group` collapses documents. A **window** keeps every document and adds a
value computed from its neighbours: running totals, previous row, rank.
"Monthly revenue, with a running total and last month's revenue":

```python
pipeline = [
    {"$group": {
        "_id": {"$dateTrunc": {"date": "$purchase_date", "unit": "month"}},
        "revenue": {"$sum": "$amount"},
    }},
    {"$setWindowFields": {
        "sortBy": {"_id": 1},
        "output": {
            "running_total": {"$sum": "$revenue",
                              "window": {"documents": ["unbounded", "current"]}},
            "prev_month": {"$shift": {"output": "$revenue", "by": -1}},
        },
    }},
]
```

```text
{'_id': datetime.datetime(2024, 1, 1, 0, 0), 'revenue': Decimal128('70521.68'), 'running_total': Decimal128('70521.68'),  'prev_month': None}
{'_id': datetime.datetime(2024, 2, 1, 0, 0), 'revenue': Decimal128('70217.53'), 'running_total': Decimal128('140739.21'), 'prev_month': Decimal128('70521.68')}
{'_id': datetime.datetime(2024, 3, 1, 0, 0), 'revenue': Decimal128('69783.42'), 'running_total': Decimal128('210522.63'), 'prev_month': Decimal128('70217.53')}
...
```

- `sortBy` is the window's `ORDER BY`. Add `partitionBy` for SQL's
  `PARTITION BY` (a running total per state, say).
- `["unbounded", "current"]` is "from the first document up to this one".
- `$shift` by -1 is SQL's `LAG()`. The first month has no previous month, so
  it gets `None`.

The catalog's Q06 (purchase streaks) and Q07 (ranked leaderboard) are built
on this stage.

### 9.2 Several reports in one pass: `$facet`

```python
result = list(db.purchases.aggregate([
    {"$facet": {
        "by_department": [{"$sortByCount": "$department"}, {"$limit": 3}],
        "by_card": [{"$sortByCount": "$card_type"}, {"$limit": 3}],
        "totals": [{"$group": {"_id": None, "revenue": {"$sum": "$amount"}}}],
    }},
]))
pprint(result[0])
```

```text
{'by_card': [{'_id': 'switch', 'count': 1265}, ...],
 'by_department': [{'_id': 'Electronics', 'count': 496}, ...],
 'totals': [{'_id': None, 'revenue': Decimal128('2194766.34')}]}
```

Each key is a complete sub-pipeline run over the same input, and the result
is **one** document holding all of them. A dashboard's worth of numbers in
one round trip. The output is still one document, so the 16 MB limit applies.

> **Exercise 17.** Which month had the biggest **drop** in revenue from the
> month before? (Hint: `$shift`, then `$set` a `change` field, then sort.)

---

## Part 10 — Is it fast?

Everything so far gives the right answer on 10,000 purchases. `idx_1m` has a
million. [§7](07_explain/) measures this properly; here's enough to read a
plan.

### 10.1 `explain()` on a `find`

```python
plan = db.purchases.find({"department": "Books"}).explain()
print(plan["queryPlanner"]["winningPlan"])
```

```text
{'stage': 'FETCH',
 'inputStage': {'stage': 'IXSCAN', 'indexName': 'department_1',
                'indexBounds': {'department': ['["Books", "Books"]']}, ...}}
```

Read plans **from the inside out**: an `IXSCAN` (index scan) on
`department_1` finds the matching entries, then `FETCH` loads each document.
Now a field with no index:

```python
plan = db.purchases.find({"product_name": "Smart Speaker 65"}).explain()
```

```text
{'stage': 'COLLSCAN', 'filter': {'product_name': {'$eq': 'Smart Speaker 65'}}, ...}
```

`COLLSCAN` (collection scan) reads **every** document and tests each one.
Fine at 10k, painful at 1m.

| Stage        | Means                                            |
| ------------ | ------------------------------------------------ |
| `COLLSCAN`   | read the whole collection                        |
| `IXSCAN`     | walk part of an index                            |
| `FETCH`      | load full documents for index entries            |
| `SORT`       | sort in memory (no index gave the order)         |
| `COUNT_SCAN` | count index entries without loading any document |

### 10.2 Pipelines use indexes only at the start

```python
plan = db.command("explain", {
    "aggregate": "purchases",
    "pipeline": [{"$match": {"department": "Books"}}, {"$count": "n"}],
    "cursor": {},
}, verbosity="queryPlanner")
```

This plan's innermost stage is a `COUNT_SCAN` on `department_1`: the count is
answered **from the index alone**, without reading a single purchase.

The rule behind that: **only the stages at the front of a pipeline, before
the first reshaping stage, can use an index.** A `$match` or `$sort` that
comes first is handed to the query planner. The same `$match` after a
`$group` or `$unwind` filters documents in memory, because the documents it
sees were computed and no index covers them.

So the stage-order advice from this handout is also performance advice:

1. **`$match` as early as possible.** Fewer documents for every later stage,
   and an index can do the filtering.
2. **`$sort` + `$limit` together.** The server keeps only the top k.
3. **`$lookup` after you've narrowed down** ([§8.2](#82-lookup-bring-in-a-document-from-another-collection)).
4. **`$project` late**, unless it drops large fields early on a big pipeline.

A `$sort` that can't use an index sorts in memory, and a single sort stage
is capped at 100 MB of memory. Past that it needs
`aggregate(pipeline, allowDiskUse=True)` (on by default in recent
versions), and spilling to disk is slow. Either way, it's a sign that an
index or an earlier `$match` is missing.

> **Exercise 18.** Run Exercise 8's history query on customer 74 with
> `.explain()`. Which index does it use, and is there a `SORT` stage? Then
> look at the index list in [build_mongo.py](05_load/build_mongo.py): is
> there an index that could deliver customer 74's purchases already in date
> order? ([§7](07_explain/) builds it.)

---

## Final challenge: three reports

Write each as one function that takes its parameters and returns a list of
dicts, with tidy field names (no bare `_id`), rounded money, and a
deterministic order.

1. **Product catalog page.** Products in a price range, sorted by price then
   name, paged with keyset pagination.
2. **Customer statement.** A customer's purchases between two dates, newest
   first, plus a summary line (count, total, average, most-used department)
   from a second query, or the same one with `$facet`.
3. **Department report.** For each department: number of purchases, revenue,
   average amount, its best-selling product, and its best state, sorted by
   revenue. Run it against `idx_1m` too, and use `explain()` to find which
   stage costs the most.

## Quick reference

```python
db.coll.find_one(filter, projection)                      # dict or None
db.coll.find(filter, projection).sort([(f, -1), ("_id", -1)]).skip(n).limit(k)   # cursor
db.coll.count_documents(filter)          db.coll.estimated_document_count()
db.coll.distinct(field, filter)          db.coll.find(...).explain()
db.coll.aggregate([stage, stage, ...])                    # cursor

# filters
{"f": v}   {"f": {"$gt": v}}   {"f": {"$in": [a, b]}}   {"$or": [{...}, {...}]}
{"a.b": v}   {"arr": {"$elemMatch": {...}}}   {"arr": {"$size": n}}   {"f": {"$exists": False}}

# stages
{"$match": filter}                        {"$sort": {"f": -1, "_id": 1}}     {"$limit": n}
{"$group": {"_id": key, "out": {"$sum": "$f"}}}           # key: None, "$f", {"a": "$a", "b": "$b"}, expression
{"$project": {"_id": 0, "new": "$old", "x": {"$round": ["$x", 2]}}}           {"$set": {...}}
{"$unwind": "$arr"}                       {"$lookup": {"from", "localField", "foreignField", "as"}}
{"$count": "n"}   {"$sortByCount": "$f"}   {"$bucket": {...}}   {"$facet": {...}}   {"$setWindowFields": {...}}

# accumulators
$sum  $avg  $min  $max  $count  $push  $addToSet  $first  $last  $top  $topN
```
